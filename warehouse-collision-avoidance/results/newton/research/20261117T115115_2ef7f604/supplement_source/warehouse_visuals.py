"""Procedural warehouse render assets; no mesh here is a Newton collider.

Every dynamic model has a body-local origin at the Newton body's centre of
mass. Its root frame receives the complete body_q pose (including rotation).
Replacing these builders with authored meshes leaves physics untouched.
"""
from functools import lru_cache

import numpy as np
import trimesh


def _paint(mesh, color):
    mesh.visual.face_colors = (*color, 255)
    return mesh


def _box(size, position, color):
    mesh = trimesh.creation.box(extents=size)
    mesh.apply_translation(position)
    return _paint(mesh, color)


def _cylinder(radius, height, position, color, wheel=False):
    mesh = trimesh.creation.cylinder(radius=radius, height=height, sections=12)
    if wheel:
        mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    mesh.apply_translation(position)
    return _paint(mesh, color)


@lru_cache(maxsize=16)
def amr_mesh(radius=.42, half_height=.26):
    teal, dark, metal = (16, 150, 137), (25, 40, 48), (201, 220, 222)
    parts = [
        _box((.60, .46, .28), (0, 0, -.04), teal),
        _box((.48, .36, .035), (0, 0, .115), metal),
        _box((.045, .43, .10), (.31, 0, -.075), dark),
        _box((.045, .43, .10), (-.31, 0, -.075), dark),
        _box((.008, .24, .025), (.335, 0, -.035), (111, 255, 196)),
        _cylinder(.035, .12, (.10, 0, .17), dark),
        _cylinder(.10, .055, (.10, 0, .23), dark),
        _cylinder(.075, .01, (.10, 0, .255), (83, 215, 231)),
    ]
    for x in (-.18, .18):
        for y in (-.245, .245):
            parts.append(_cylinder(.11, .055, (x, y, -.15), dark, wheel=True))
            parts.append(_cylinder(.055, .058, (x, y, -.15), metal, wheel=True))
    mesh = trimesh.util.concatenate(parts)
    mesh.apply_scale([radius/.42, radius/.42, half_height/.26])
    return mesh


@lru_cache(maxsize=16)
def worker_mesh(radius=.30, half_height=.55):
    orange, navy, skin, yellow = (238, 121, 35), (35, 56, 76), (224, 170, 130), (250, 206, 45)
    parts = [
        _box((.34, .24, .50), (0, 0, .15), orange),
        _box((.345, .245, .035), (0, 0, .28), (228, 243, 219)),
        _box((.345, .245, .035), (0, 0, .03), yellow),
        _box((.30, .23, .15), (0, 0, -.17), navy),
        _cylinder(.075, .10, (0, 0, .48), skin),
    ]
    head = trimesh.creation.icosphere(subdivisions=1, radius=.14)
    head.apply_translation((0, 0, .67))
    parts.append(_paint(head, skin))
    parts.append(_cylinder(.16, .10, (0, 0, .80), yellow))
    for sign in (-1, 1):
        parts.extend([
            _box((.085, .15, .40), (sign*.217, 0, .12), orange),
            _box((.075, .13, .10), (sign*.217, 0, -.12), skin),
            _box((.115, .16, .50), (sign*.09, 0, -.49), navy),
            _box((.13, .25, .11), (sign*.09, .025, -.795), (24, 32, 38)),
        ])
    mesh = trimesh.util.concatenate(parts)
    # Match the capsule's total height and width rather than scaling an
    # unrelated marker in world coordinates.
    mesh.apply_scale([radius/.30, radius/.30, (2*(radius+half_height))/1.70])
    return mesh


@lru_cache(maxsize=16)
def rack_mesh(width, depth, height):
    parts = []
    blue, beam, deck, carton = (49, 88, 119), (233, 143, 40), (150, 169, 175), (179, 129, 77)
    bays = max(1, int(round(depth / 1.75)))
    for y in np.linspace(-depth/2+.08, depth/2-.08, bays+1):
        for x in (-width/2+.08, width/2-.08):
            parts.append(_box((.12, .12, height), (x, y, height/2), blue))
    for level in (.15, height*.38, height*.70):
        parts.append(_box((width-.10, depth-.10, .08), (0, 0, level), deck))
        for x in (-width/2+.08, width/2-.08):
            parts.append(_box((.12, depth-.10, .13), (x, 0, level+.04), beam))
        for i in range(bays):
            y = -depth/2 + (i+.5)*depth/bays
            parts.append(_box((width*.67, depth/bays*.67, .55), (0, y, level+.33), carton))
            parts.append(_box((width*.68, .05, .55), (0, y, level+.33), (218, 186, 129)))
    return trimesh.util.concatenate(parts)


class WarehouseVisuals:
    def __init__(self, viewer, metadata):
        self.viewer, self.metadata = viewer, metadata
        self.scene = viewer.server.scene
        # Native shapes remain in Newton and Contacts, but are not drawn over
        # the independent render assets.
        viewer.show_visual = False
        viewer.show_collision = False
        viewer.show_ground = False
        self.scene.add_light_ambient("/warehouse/lights/fill", intensity=1.5)
        width, height = metadata["width"], metadata["height"]
        self.scene.add_mesh_trimesh("/warehouse/models/floor",
            _box((width, height, .08), (width/2, height/2, -.04), (222, 235, 231)))
        paint = (metadata.get("map_config") or {}).get("aislePaint")
        if not metadata.get("map_config") and metadata.get("layout_version", 1) >= 2:
            paint = {"width":5.8, "centreY":height/2}
        if paint:
            self.scene.add_mesh_trimesh("/warehouse/models/main_aisle",
                _box((width-.4, paint["width"], .008), (width/2, paint["centreY"], .008), (194, 223, 215)))
        wall_height = metadata.get("wall_height_m", 1.6)
        walls = [
            ((width, .3, wall_height), (width/2, -.15, wall_height/2)),
            ((width, .3, wall_height), (width/2, height+.15, wall_height/2)),
            ((.3, height, wall_height), (-.15, height/2, wall_height/2)),
            ((.3, height, wall_height), (width+.15, height/2, wall_height/2)),
        ]
        for i, (size, position) in enumerate(walls):
            self.scene.add_mesh_trimesh(f"/warehouse/models/wall-{i}", _box(size, position, (123, 157, 152)))
        poses = metadata.get("shelf_poses") or [
            {"position":[x+w/2,y+d/2], "rotation":0, "size":[w,d]}
            for x,y,w,d in metadata["shelves"]]
        self.racks = []
        for i, shelf in enumerate(poses):
            w, d = shelf["size"]
            x, y = shelf["position"]
            angle = np.radians(shelf["rotation"])/2
            self.racks.append(self.scene.add_mesh_trimesh(f"/warehouse/models/rack-{i}",
                (_box((w,d,1.2),(0,0,.6),(110,120,130)) if shelf.get("kind") == "barrier"
                 else rack_mesh(w, d, metadata.get("shelf_height_m", 1.5))),
                position=(x, y, 0), wxyz=(np.cos(angle),0,0,np.sin(angle))))
        self.roots = {}
        for body in metadata["bodies"]:
            name = "/warehouse/models/agents/" + body["id"]
            self.roots[body["id"]] = self.scene.add_frame(name, show_axes=False)
            half_height = body.get("collider_half_height",
                                   .3 if body["kind"] == "worker" else body["radius"])
            mesh = (worker_mesh if body["kind"] == "worker" else amr_mesh)(body["radius"], half_height)
            self.scene.add_mesh_trimesh(name + "/mesh", mesh)
        self.update(metadata.get("initial_body_q", []))

    def update(self, body_q):
        if not len(body_q):
            return
        for body in self.metadata["bodies"]:
            q = body_q[body["body"]]
            root = self.roots[body["id"]]
            root.position = tuple(q[:3])
            root.wxyz = (q[6], q[3], q[4], q[5])
