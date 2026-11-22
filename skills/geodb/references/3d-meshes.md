# 3D meshes: build one in your own sandbox and draw it in the project's 3D

Needs a code sandbox that can call the API. Pull the samples, build a mesh (a grade shell, a surface) as you judge best, write it in the project's local grid as one .glb, check it, upload it as a project file and attach it as a MeshLayer; it is a visualisation, not a resource estimate.

### Making the mesh

This needs a code sandbox that can call the API (`session_key`); without one,
say so. geoDB computes nothing here: you build the mesh, geoDB keeps it, draws
it in the project's 3D, and can undo it.

1. **Pull what it needs,** filtered (topic `working-efficiently`): the drill
   samples of one sampling pass and their laboratory values (topic
   `geostatistics`). Each drill sample's `xyz_from` / `xyz_to` is already in
   the mesh's frame (step 4).
2. **Compute it as you judge best.** Suggestions only: scipy (interpolation),
   scikit-image or pyvista (isosurfaces), trimesh (checks, the `.glb`),
   gstlearn (variograms, kriging), LoopStructural (stratigraphy). Note the
   method and its parameters.
3. **The user sets the cutoff.** Ask and confirm it; never take it from a
   percentile (on data with two populations a percentile falls between them).
   Use drill samples only unless the user says otherwise, and never pool
   populations (drilling with surface samples, field XRF with laboratory
   values, two sampling passes) without saying so and their yes. Say how
   below-detection results were treated: for example half the detection limit
   when one is on file; otherwise say none is on file and what you assumed.
4. **The frame:** the project's local grid, Z up, with X, Y and Z all in the
   grid's own length unit (feet on a feet grid: the `local_grid` frame of a
   hole's `drill-collars/<id>/trace/` names `xy_unit` and `z_unit`). Built
   from `xyz_from` / `xyz_to`, points are already there. Otherwise read
   `projects/<id>/coordinate-system/`: take the points into `crs_epsg`,
   subtract `origin_x` / `origin_y` (dx, dy), turn them clockwise by
   `rotation_degrees` (r): x = dx cos r + dy sin r, y = -dx sin r + dy cos r.
   Z is the elevation (served in metres) in the grid's unit: inside the mesh
   file is the one place you convert. A project with no grid, or a custom
   calibrated mine grid (that read answers `null`), cannot take a mesh yet.
5. **One self-contained `.glb`:** vertex positions written as computed, no
   node transforms, nothing outside the file. Plain geometry only: no
   compression (Draco), no image textures, no instancing; colour it with
   vertex colours or a material's base colour. Many exporters turn Z-up into
   Y-up by default: switch that off, or the mesh lies on its side.
6. **Check before you push, and report each:** the bounds sit inside the
   drilled volume (against the samples' `xyz_from` range); the mesh is closed
   and clean (watertight, no degenerate faces); it honours the data (the share
   of samples at or above the cutoff that fall inside it, and below it that
   fall outside); under 100 MB and 2,000,000 triangles; its volume, with no
   tonnage or grade claim.

### Drawing it in the project's 3D

1. **Upload the `.glb` as a project file** (the rules' "Uploading files":
   `ProjectFile` `upload_start`, PUT the blocks, `upload_commit`). If your
   sandbox cannot reach the storage host, the user uploads it on the web and
   you find its id in `project-files/`.
2. **Attach it:** a `MeshLayer` `create` with `project`, `project_file` (that
   id), `name` and `method` (how it was made, in a sentence or two;
   `records/describe/MeshLayer/` is the contract). Run its dry run first and
   read it (triangles, bounds, warnings).
   **One yes covers both steps:** once the user asked to see it in 3D and
   confirmed the cutoff, upload and attach in one go. Ask again only if a
   check failed or the dry run returned a warning.
3. **Then tell the user plainly** what you did: what you built, from which
   data, cutoff and method, and what each check found; hand them the
   answer's `url`, which opens the project's 3D with the mesh shown. To make
   it part of a named view others open, save a view (topic `views`). Always
   say: an interpolated surface for visualisation, not a mineral resource
   estimate. Undo takes it back.
4. **A new version** is an `update` of the layer (`id`) naming the new file
   in `project_file`, never a second layer. `retract` (with `"confirm":
   "retract"`) moves a layer to the Trash. `mesh-layers/?project=<id>` lists
   the project's meshes and why one is not drawn.
5. **Refusals and warnings carry their remedy.** A refused file
   (`mesh_not_glb`, `mesh_too_large`, `mesh_too_many_triangles`,
   `mesh_not_self_contained`, `mesh_extension_unsupported`, `mesh_empty`):
   fix it and upload again. `mesh_frame_unavailable`: this project cannot
   take a mesh yet; tell the user. A warning keeps the layer but says it is
   probably misplaced: `mesh_outside_project` (map coordinates, not the local
   grid), `mesh_elevation_mismatch` (a Y-up export) or
   `mesh_placement_unchecked` (node transforms or no bounds in the file); fix
   the file and `update` the layer with it.
