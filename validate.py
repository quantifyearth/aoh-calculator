import glob
import os
import sys

from yirgacheffe.layers import RasterLayer

if __name__ == "__main__":
    folder_a = sys.argv[1]
    folder_b = sys.argv[2]

    a_files = glob.glob("*.tif", root_dir=folder_a)
    b_files = glob.glob("*.tif", root_dir=folder_b)
    assert set(a_files) == set(b_files), "Directories don't match"

    for filename in a_files:
        a_path = os.path.join(folder_a, filename)
        b_path = os.path.join(folder_b, filename)

        a_raster = RasterLayer.layer_from_file(a_path)
        b_raster = RasterLayer.layer_from_file(b_path)

        if a_raster.window != b_raster.window:
            print(filename)
            print(a_raster.window)
            print(b_raster.window)
            continue

        if a_raster.area != b_raster.area:
            print(filename)
            print(a_raster.area)
            print(b_raster.area)

        else:
            print("boo")
