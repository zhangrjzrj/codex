import os
import cc

base_dir = os.environ.get("MESSIAH_CODEX_BUILD_DIR", "")
marker = os.path.join(base_dir, "nbs_attach_running_scene.marker.txt")
video_path = os.environ.get("MESSIAH_NBS_VIDEO", "Videos/H74.nbs")


def write_marker(line):
    with open(marker, "a") as fp:
        fp.write(line + "\n")


print("LOAD_ATTACH_SCRIPT_SUCCESS")
write_marker("script-enter")

director = cc.Director.getInstance()
if not director:
    write_marker("no-director")
    raise RuntimeError("Director unavailable")

scene = director.getRunningScene()
if not scene:
    write_marker("no-running-scene")
    raise RuntimeError("Running scene unavailable")

size = director.getOpenGLView().getDesignResolutionSize()
write_marker("scene-ok %.0fx%.0f" % (size.width, size.height))


def start_cb(node, total_time, total_frames):
    write_marker("start-cb time=%s frames=%s" % (total_time, total_frames))


gif_node = cc.MiniGifNode.create(video_path, False, 0, False, start_cb, "")
if not gif_node:
    write_marker("create-failed")
else:
    write_marker("create-ok decoder=%s" % gif_node.getDecoderId())
    gif_node.setLoop(True)
    gif_node.setContentSize(cc.Size(size.width, size.height))
    gif_node.setAnchorPoint(cc.Vec2(0.5, 0.5))
    gif_node.setPosition(cc.Vec2(size.width / 2, size.height / 2))
    gif_node.setVisible(True)
    scene.addChild(gif_node)
    write_marker("add-child-ok")
