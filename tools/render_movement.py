import json
from PIL import Image, ImageDraw, ImageColor

SCALING_FACTOR = 4

with open("env_db.json", "r") as f:
    env_db = json.load(f)

meta_data = json.loads(env_db["meta_data"])
x_dim = meta_data["x_dim"] * SCALING_FACTOR
y_dim = meta_data["y_dim"] * SCALING_FACTOR
agent_vision_radius = meta_data["agent_vision_radius"] * SCALING_FACTOR
persona_names = meta_data["persona_names"]
colors = list(ImageColor.colormap.keys())
# persona_colors = {p: c for p, c in zip(persona_names, colors)}
persona_colors = {p: "green" for p, c in zip(persona_names, colors)}

frame_size = (x_dim, y_dim)
start_time = float("inf")
end_time = 0
num_frames = 0
personas = {p: {} for p in persona_names}

for k, v in env_db.items():
    if "action:" in k:
        persona, step, base_step = k.split(":")[1:]
        assert persona in persona_names
        action_info = json.loads(v)
        step, base_step = int(step), int(base_step)
        effective_time = action_info["effective_time"]
        cluster_action_counter = action_info["cluster_action_counter"]
        num_frames = max(num_frames, cluster_action_counter)
        start_time = min(start_time, effective_time)
        end_time = max(end_time, effective_time)
        if action_info["type"] == "AgentMove":
            x, y = json.loads(v)["movement"]
            x *= SCALING_FACTOR
            y *= SCALING_FACTOR
            personas[persona][cluster_action_counter] = (x, y, step - base_step)
    elif ":init_info" in k:
        persona = k.split(":")[1]
        init_info = json.loads(v)
        personas[persona]["last_frame"] = (init_info["x"] * SCALING_FACTOR, init_info["y"] * SCALING_FACTOR, 0)
    else:
        continue


def create_frame(frame_number):
    # Create a new image with white background
    image = Image.new('RGB', frame_size, 'white')
    draw = ImageDraw.Draw(image)

    acting = False
    for p, v in personas.items():
        if frame_number not in v:
            x, y, step_diff = v["last_frame"]
            acting = False
        else:
            x, y, step_diff = v[frame_number]
            personas[p]["last_frame"] = (x, y, step_diff)
            acting = True
        expand_vision = agent_vision_radius + step_diff * SCALING_FACTOR
        bounding_box = [x - expand_vision, y - expand_vision, x + expand_vision, y + expand_vision]
        draw.ellipse(bounding_box, outline=persona_colors[p] if not acting else "black", width=1)
        draw.point((x, y), fill="red")
    return image


# Generate and save each frame
frames = []
for frame_number in range(num_frames):
    frame = create_frame(frame_number)
    # frame.save(f'frame_{frame_number:03d}.png')  # Save frame as PNG
    frames.append(frame)

# Optionally, create an animated GIF
frames[0].save('animation.gif', save_all=True, append_images=frames[1:], optimize=False, duration=100, loop=0)
