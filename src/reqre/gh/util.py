# util.py
import json
import math
import os
import re

import rhino3dm as r3d


def decode_inner_tree(inner_tree):
    objs = []
    for _, items in inner_tree.items():
        for item in items:
            data = json.loads(item["data"])
            obj = r3d.CommonObject.Decode(data)
            if obj is not None:
                objs.append(obj)
    return objs


def get_output_by_name(values, wanted_name):
    matches = [
        v
        for v in values
        if v["ParamName"] == wanted_name or v["ParamName"].endswith(":" + wanted_name)
    ]
    objs = []
    for v in matches:
        objs.extend(decode_inner_tree(v["InnerTree"]))
    return objs


def extract_plane(values, ParamName):
    """
    values: Resthopper 'values' array
    returns: r3d.Plane or None
    """
    inner_tree = None
    for entry in values:
        name = entry["ParamName"]  # e.g. "RH_OUT:interface1"
        if ParamName in name:
            inner_tree = entry["InnerTree"]
            break
    if inner_tree is None:
        return None

    for _, items in inner_tree.items():
        for item in items:
            if "Plane" not in item.get("type", ""):
                continue

            data = item.get("data")

            # 1) JSON string?
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    nums = re.findall(
                        r"(-?\d+(?:\.\d+)?(?:e[+-]?\d+)?)", data, flags=re.I
                    )
                    if len(nums) >= 9:
                        f = list(map(float, nums[:9]))
                        o = r3d.Point3d(f[0], f[1], f[2])
                        x = r3d.Vector3d(f[3], f[4], f[5])
                        y = r3d.Vector3d(f[6], f[7], f[8])
                        return r3d.Plane(o, x, y)
                    else:
                        continue

            # 2) Dict payload
            if isinstance(data, dict):

                def pick(v):
                    if isinstance(v, list) and len(v) == 3:
                        return v
                    if isinstance(v, dict):
                        X = v.get("X", v.get("x"))
                        Y = v.get("Y", v.get("y"))
                        Z = v.get("Z", v.get("z"))
                        if X is not None and Y is not None and Z is not None:
                            return [X, Y, Z]
                    return None

                origin_raw = data.get("Origin", data.get("origin"))
                x_axis_raw = data.get("XAxis", data.get("xaxis"))
                y_axis_raw = data.get("YAxis", data.get("yaxis"))

                origin_vec, x_axis_vec, y_axis_vec = (
                    pick(origin_raw),
                    pick(x_axis_raw),
                    pick(y_axis_raw),
                )
                if origin_vec and x_axis_vec and y_axis_vec:
                    origin = r3d.Point3d(*map(float, origin_vec))
                    x_axis = r3d.Vector3d(*map(float, x_axis_vec))
                    y_axis = r3d.Vector3d(*map(float, y_axis_vec))
                    return r3d.Plane(origin, x_axis, y_axis)

    return None


# ---------- Plane helpers (no FitPlaneToPoints) ----------


def _vec(a, b):
    return r3d.Vector3d(b.X - a.X, b.Y - a.Y, b.Z - a.Z)


def _vlen(v):
    return math.sqrt(v.X * v.X + v.Y * v.Y + v.Z * v.Z)


def _vunit(v):
    length = _vlen(v)
    if length == 0.0:
        return r3d.Vector3d(0, 0, 0)
    return r3d.Vector3d(v.X / length, v.Y / length, v.Z / length)


def plane_from_points(pts):
    if len(pts) < 3:
        raise ValueError("Need at least 3 points to define a plane")

    cx = sum(p.X for p in pts) / len(pts)
    cy = sum(p.Y for p in pts) / len(pts)
    cz = sum(p.Z for p in pts) / len(pts)
    c = r3d.Point3d(cx, cy, cz)

    v1 = None
    max_d = -1.0
    for p in pts:
        v = _vec(c, p)
        d = _vlen(v)
        if d > max_d:
            max_d = d
            v1 = v
    if max_d < 1e-9:
        raise ValueError("Points are degenerate (all identical)")

    best_area = -1.0
    v2 = None
    for p in pts:
        w = _vec(c, p)
        cp = r3d.Vector3d.CrossProduct(v1, w)
        area = _vlen(cp)
        if area > best_area:
            best_area = area
            v2 = w
    if best_area < 1e-12:
        raise ValueError("Points are collinear; cannot determine a plane")

    n = r3d.Vector3d.CrossProduct(v1, v2)
    n = _vunit(n)

    try:
        plane = r3d.Plane(c, n)
    except Exception:
        x_guess = r3d.Vector3d(1, 0, 0)
        dot = abs(n.X * x_guess.X + n.Y * x_guess.Y + n.Z * x_guess.Z)
        if dot > 0.9:
            x_guess = r3d.Vector3d(0, 1, 0)
        x_axis = r3d.Vector3d.CrossProduct(n, x_guess)
        x_axis = _vunit(x_axis)
        y_axis = r3d.Vector3d.CrossProduct(n, x_axis)
        plane = r3d.Plane(c, x_axis, y_axis)
    return plane


def _tx_point(p: r3d.Point3d, xf: r3d.Transform) -> r3d.Point3d:
    return r3d.Point3d(
        xf.M00 * p.X + xf.M01 * p.Y + xf.M02 * p.Z + xf.M03,
        xf.M10 * p.X + xf.M11 * p.Y + xf.M12 * p.Z + xf.M13,
        xf.M20 * p.X + xf.M21 * p.Y + xf.M22 * p.Z + xf.M23,
    )


def transform_plane(pl: r3d.Plane, xf: r3d.Transform) -> r3d.Plane:
    o = r3d.Point3d(pl.Origin.X, pl.Origin.Y, pl.Origin.Z)
    px = r3d.Point3d(
        pl.Origin.X + pl.XAxis.X, pl.Origin.Y + pl.XAxis.Y, pl.Origin.Z + pl.XAxis.Z
    )
    py = r3d.Point3d(
        pl.Origin.X + pl.YAxis.X, pl.Origin.Y + pl.YAxis.Y, pl.Origin.Z + pl.YAxis.Z
    )

    o = _tx_point(o, xf)
    px = _tx_point(px, xf)
    py = _tx_point(py, xf)

    x2 = r3d.Vector3d(px.X - o.X, px.Y - o.Y, px.Z - o.Z)
    y2 = r3d.Vector3d(py.X - o.X, py.Y - o.Y, py.Z - o.Z)
    return r3d.Plane(o, x2, y2)


def transform_component(comp: dict, xf: r3d.Transform) -> dict:
    comp["brep"].Transform(xf)
    for idx, iface in enumerate(comp["iface_list"]):
        comp["iface_list"][idx] = transform_plane(iface, xf)
    return comp


def align_component(comp: dict, src_plane: r3d.Plane, dst_plane: r3d.Plane) -> dict:
    t = r3d.Transform.PlaneToPlane(src_plane, dst_plane)
    if not t.IsValid:
        raise Exception("Invalid PlaneToPlane transform")
    return transform_component(comp, t)


def plane_to_surface(
    plane: r3d.Plane,
    width: float = 1.0,
    height: float | None = None,
    as_brep: bool = False,
):
    if height is None:
        height = width
    u = r3d.Interval(-width * 0.5, width * 0.5)
    v = r3d.Interval(-height * 0.5, height * 0.5)
    srf = r3d.PlaneSurface(plane, u, v)
    if as_brep:
        return r3d.Brep.CreateFromSurface(srf)
    return srf


def vector_between_points(p1: r3d.Point3d, p2: r3d.Point3d) -> r3d.Vector3d:
    return r3d.Vector3d(p2.X - p1.X, p2.Y - p1.Y, p2.Z - p1.Z)


# ---------- Bridge-specific math helpers (parameterized) ----------


def radius_from_chords(n_segments: int, as_length: float) -> float:
    """
    Radius of a half-circle approximated by N equal chords of length as_length.
    """
    if n_segments <= 0 or as_length <= 0:
        raise ValueError("n_segments and as_length must be positive.")
    return as_length / (2 * math.sin(math.pi / (2 * n_segments)))


def sp_length_at_station(
    station: int, n_segments: int, as_length: float, offset: float = 500.0
) -> float:
    """
    Vertical distance from semicircle to apex height (y=r) at a given station.
    """
    if not (0 <= station <= n_segments):
        raise ValueError("station must be between 0 and n_segments (inclusive)")
    r = radius_from_chords(n_segments, as_length)
    return r * (1 - math.sin(station * math.pi / n_segments)) + offset


def rotation_deg(
    degrees: float, axis: r3d.Vector3d | None = None, pivot: r3d.Point3d | None = None
) -> r3d.Transform:
    if axis is None:
        axis = r3d.Vector3d(0, 1, 0)
    if pivot is None:
        pivot = r3d.Point3d(0, 0, 0)
    return r3d.Transform.Rotation(math.radians(degrees), axis, pivot)


# ---------- OBJ export helpers ----------


def _brep_meshes(brep: r3d.Brep):
    if hasattr(r3d.Mesh, "CreateFromBrep"):
        try:
            mp = r3d.MeshingParameters.Default
            meshes = r3d.Mesh.CreateFromBrep(brep, mp)
        except Exception:
            meshes = r3d.Mesh.CreateFromBrep(brep)
        return meshes or []

    try:
        import compute_rhino3d.Mesh as cr_mesh
    except Exception as exc:
        raise RuntimeError(
            "No mesh creation API found in rhino3dm; install a newer rhino3dm "
            "or ensure compute_rhino3d is available."
        ) from exc

    meshes = cr_mesh.CreateFromBrep(brep)
    return meshes or []


def write_obj(path: str, breps: list[r3d.Brep]) -> None:
    out_dir = os.path.dirname(path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        f.write("# gh-assembler OBJ export\n")
        vertex_offset = 0
        obj_index = 0

        def _count(seq):
            if hasattr(seq, "Count"):
                return seq.Count
            try:
                return len(seq)
            except Exception:
                return 0

        def _item(seq, idx):
            try:
                return seq[idx]
            except Exception:
                return seq.Item(idx)

        def _face_indices(face):
            if hasattr(face, "A"):
                a, b, c = face.A, face.B, face.C
                if getattr(face, "IsQuad", False):
                    return [a, b, c, face.D]
                return [a, b, c]
            if isinstance(face, (list, tuple)):
                if len(face) >= 4:
                    return [face[0], face[1], face[2], face[3]]
                if len(face) == 3:
                    return [face[0], face[1], face[2]]
            raise TypeError("Unsupported face type in mesh")

        for brep in breps:
            meshes = _brep_meshes(brep)
            for mesh in meshes:
                obj_index += 1
                f.write(f"o Brep_{obj_index}\n")

                vcount = _count(mesh.Vertices)
                for i in range(vcount):
                    v = _item(mesh.Vertices, i)
                    f.write(f"v {v.X} {v.Y} {v.Z}\n")

                fcount = _count(mesh.Faces)
                for i in range(fcount):
                    face = _item(mesh.Faces, i)
                    idxs = _face_indices(face)
                    idxs = [vertex_offset + int(i) + 1 for i in idxs]
                    if len(idxs) == 4:
                        f.write(f"f {idxs[0]} {idxs[1]} {idxs[2]} {idxs[3]}\n")
                    else:
                        f.write(f"f {idxs[0]} {idxs[1]} {idxs[2]}\n")

                vertex_offset += vcount


def write_stl(path: str, breps: list[r3d.Brep]) -> None:
    out_dir = os.path.dirname(path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    def _count(seq):
        if hasattr(seq, "Count"):
            return seq.Count
        try:
            return len(seq)
        except Exception:
            return 0

    def _item(seq, idx):
        try:
            return seq[idx]
        except Exception:
            return seq.Item(idx)

    def _face_indices(face):
        if hasattr(face, "A"):
            a, b, c = face.A, face.B, face.C
            if getattr(face, "IsQuad", False):
                return [a, b, c, face.D]
            return [a, b, c]
        if isinstance(face, (list, tuple)):
            if len(face) >= 4:
                return [face[0], face[1], face[2], face[3]]
            if len(face) == 3:
                return [face[0], face[1], face[2]]
        raise TypeError("Unsupported face type in mesh")

    def _normal(p0, p1, p2):
        ux, uy, uz = p1.X - p0.X, p1.Y - p0.Y, p1.Z - p0.Z
        vx, vy, vz = p2.X - p0.X, p2.Y - p0.Y, p2.Z - p0.Z
        nx = uy * vz - uz * vy
        ny = uz * vx - ux * vz
        nz = ux * vy - uy * vx
        length = math.sqrt(nx * nx + ny * ny + nz * nz)
        if length == 0.0:
            return 0.0, 0.0, 0.0
        return nx / length, ny / length, nz / length

    with open(path, "w", encoding="utf-8") as f:
        f.write("solid gh-assembler\n")
        for brep in breps:
            meshes = _brep_meshes(brep)
            for mesh in meshes:
                vcount = _count(mesh.Vertices)
                verts = [_item(mesh.Vertices, i) for i in range(vcount)]

                fcount = _count(mesh.Faces)
                for i in range(fcount):
                    face = _item(mesh.Faces, i)
                    idxs = _face_indices(face)
                    if len(idxs) == 3:
                        tris = [idxs]
                    else:
                        tris = [
                            [idxs[0], idxs[1], idxs[2]],
                            [idxs[0], idxs[2], idxs[3]],
                        ]

                    for a, b, c in tris:
                        p0, p1, p2 = verts[int(a)], verts[int(b)], verts[int(c)]
                        nx, ny, nz = _normal(p0, p1, p2)
                        f.write(f"  facet normal {nx} {ny} {nz}\n")
                        f.write("    outer loop\n")
                        f.write(f"      vertex {p0.X} {p0.Y} {p0.Z}\n")
                        f.write(f"      vertex {p1.X} {p1.Y} {p1.Z}\n")
                        f.write(f"      vertex {p2.X} {p2.Y} {p2.Z}\n")
                        f.write("    endloop\n")
                        f.write("  endfacet\n")
        f.write("endsolid gh-assembler\n")
