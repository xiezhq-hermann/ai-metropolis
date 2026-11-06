import ast
import json
import argparse
from PIL import Image, ImageDraw


def change_format(movements, base_step=0, target_step=8640):
    personas = {}
    min_step, max_step = float("inf"), 0
    for key in movements:
        _, persona, step = key.split(":")
        step = int(step)
        min_step = min(min_step, step)
        max_step = max(max_step, step)
        if persona not in personas:
            personas[persona] = {step: ast.literal_eval(movements[key]["location"])}
        else:
            assert step not in personas[persona]
            personas[persona][step] = ast.literal_eval(movements[key]["location"])
    print("min and max steps:", min_step, max_step)
    assert min_step <= base_step
    assert max_step > target_step
    movements = {}
    for persona in personas:
        movements[persona] = [personas[persona][i] for i in range(base_step, target_step + 1)]
    return movements, max_step


def generate_missed_steps(start_position, end_position):
    x_diff = end_position[0] - start_position[0]
    y_diff = end_position[1] - start_position[1]
    missed_steps = []
    abs_diff = abs(x_diff) + abs(y_diff)
    assert abs_diff > 1

    for i in range(1, abs(x_diff) + 1):
        direction = 1 if x_diff > 0 else -1
        missed_steps.append([start_position[0] + i * direction, start_position[1]])

    for i in range(1, abs(y_diff) + 1):
        direction = 1 if y_diff > 0 else -1
        missed_steps.append([end_position[0], start_position[1] + i * direction])

    assert missed_steps[-1] == end_position
    return missed_steps[:-1]


def validation(movements, output_file):
    persona_missed_steps = {}
    for persona in movements:
        last_x, last_y = movements[persona][0]
        for i in range(1, len(movements[persona])):
            if abs(movements[persona][i][0] - last_x) + abs(movements[persona][i][1] - last_y) > 1:
                # print(persona, i, movements[persona][i], last_x, last_y)
                missed_steps = generate_missed_steps((last_x, last_y), movements[persona][i])
                if persona not in persona_missed_steps:
                    persona_missed_steps[persona] = {i: missed_steps}
                else:
                    assert i not in persona_missed_steps[persona]
                    persona_missed_steps[persona][i] = missed_steps
            last_x, last_y = movements[persona][i]
    print("Missed steps:", persona_missed_steps)

    for p, steps in persona_missed_steps.items():
        for i, missed_steps in steps.items():
            for position in missed_steps[::-1]:
                movements[p].insert(i, position)
    for p in movements:
        movements[p] = movements[p][:8641]
    json.dump(movements, open(output_file, "w"))
    return movements


def render_movements(movements,
                     scaling_factor=4,
                     map_width=140,
                     map_height=100,
                     frame_duration=1,
                     interval=(1440, 8640)):
    scaled_width = map_width * scaling_factor
    scaled_height = map_height * scaling_factor

    def create_frame(agent_positions, width, height, scale, step):
        # Create a new image with a white background
        image = Image.new('RGB', (width, height), 'white')
        draw = ImageDraw.Draw(image)

        # Draw each agent's position
        for positions in agent_positions.values():
            x, y = positions
            scaled_x, scaled_y = x * scale, y * scale
            draw.ellipse((scaled_x - 2, scaled_y - 2, scaled_x + 2, scaled_y + 2), fill='red')
        draw.text((20, 10), f"Time: {step//360}:{(step//6) % 60}:{(step *10)% 60}", fill='black')

        return image

    # Generate frames
    frames = []
    for step in range(*interval):
        step_positions = {agent: positions[step] for agent, positions in movements.items()}
        frame = create_frame(step_positions, scaled_width, scaled_height, scaling_factor, step)
        frames.append(frame)

    # Save frames as a GIF
    output_path = 'agent_movement.gif'
    frames[0].save(output_path, save_all=True, append_images=frames[1:], duration=frame_duration, loop=0)


if __name__ == '__main__':

    parser = argparse.ArgumentParser(allow_abbrev=True)
    parser.add_argument("-f", "--movement-file", type=str, help="input file")
    parser.add_argument("-b", "--base-step", type=int, default=0, help="base step")
    parser.add_argument("-t", "--target-step", type=int, default=8640, help="target step")
    parser.add_argument("-o", "--output-file", type=str, default="new_movements.json", help="output file")

    movement_json = json.load(open(parser.parse_args().movement_file, "r"))
    movements, num_steps = change_format(movement_json, parser.parse_args().base_step, parser.parse_args().target_step)
    new_movement = validation(movements, parser.parse_args().output_file)
