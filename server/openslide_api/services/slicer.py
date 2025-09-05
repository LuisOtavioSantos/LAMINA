from pylibCZIrw import czi as pyczi

def slice_czi_image(filepath, output_dim=(1024, 1024)):
    with pyczi.open_czi(filepath) as czidoc:
        total_bounding_box = czidoc.total_bounding_box
        scenes_bounding_rectangle = czidoc.scenes_bounding_rectangle

        slices_info = {}
        scene_index = 0

        for scene, bounding_rect in scenes_bounding_rectangle.items():
            scene_slices = []
            x_start, y_start = bounding_rect.x, bounding_rect.y
            x_end, y_end = x_start + bounding_rect.w, y_start + bounding_rect.h

            num_slices_x = (x_end - x_start) // output_dim[0]
            num_slices_y = (y_end - y_start) // output_dim[1]

            for i in range(num_slices_x):
                for j in range(num_slices_y):
                    roi = (
                        x_start + i * output_dim[0],
                        y_start + j * output_dim[1],
                        output_dim[0],
                        output_dim[1]
                    )
                    scene_slices.append({'roi': roi, 'scene': scene})

            slices_info[f'scene_{scene_index}'] = scene_slices
            scene_index += 1

    return slices_info
