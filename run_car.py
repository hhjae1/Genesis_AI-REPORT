import genesis as gs

gs.init(backend=gs.gpu)
scene = gs.Scene(show_viewer=True)

car = scene.add_entity(gs.morphs.URDF(
    file="car1.urdf",
    collision=True,
    requires_jac_and_IK=True
))

scene.add_entity(gs.morphs.Plane())
scene.build()

for i in range(500):
    scene.step()
