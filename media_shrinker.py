"""
python media_shrinker.py source destination

E.g.
python media_shrinker.py "/d/media/camera" "/d/sync/send - smaller_media"

This script is meant to convert media files from a source directory into
roughly equivalent but smaller files in the destination direction.

Uses ImageMagick to convert images and ffmpeg for videos, converting them down
to Full HD resolution. Care is taken to copy the creation and modification times
of the original files. Non-media files are copied as-is.

This script was written as a hacky way of keeping all my photos and videos in my
storage-challenged phone, without relying on Google Photos or other cloud
services.
"""
import os
import datetime
import mimetypes
from shutil import copy2
from pathlib import Path
from subprocess import run, CalledProcessError

def shrink_image(source_path, destination_path):
    """
    Shrinks an image by resizing its dimensions by up to 1920x1920, keeping its
    aspect ratio.
    """
    run(['magick', 'convert', '-resize', '1920x1920>', source_path, destination_path], check=True, capture_output=True)
    # ImageMagick is not cleaning temporary files, sometimes generating 30 GB
    # files that are simply left behind. Go over these files and delete them.
    for temp_file in (Path.home() / 'AppData/Local/Temp').glob('magick-*'):
        temp_file.unlink()


def shrink_video(source_path, destination_path):
    """
    Shrinks a video by converting it h264 with resolution up to 1920x1920
    while keeping its aspect ratio.
    """
    def apply_ffmpeg(is_hardware_accelerated):
        # Settings optimized and tested for my computer
        # (AMD Ryzen 5 3600, GeForce GTX 1080 Ti), with a custom build of
        # ffmpeg to get GPU acceleration.
        # Potentially up to minutes per file, depending on original quality
        # and length.
        run([
            "C:/Program Files/ffmpeg/bin/ffmpeg.exe",
            '-noautorotate',
            '-vsync', '0',
            '-hwaccel', 'nvdec',
            '-hwaccel_output_format', 'cuda',
            *(['-c:v', 'h264_cuvid'] if is_hardware_accelerated else []),
            '-i', source_path,
            '-c:v', 'hevc_nvenc',
            '-crf', '30', # Video quality is defined here.
            '-c:a', 'copy',
            '-vf', 'scale_cuda=1920:1920:force_original_aspect_ratio=decrease',
            '-movflags', 'use_metadata_tags', '-map_metadata', '0',
            '-f', 'mp4',
            '-y',
            destination_path,
        ], check=True, capture_output=True)

    try:
        apply_ffmpeg(is_hardware_accelerated=True)
    except CalledProcessError:
        apply_ffmpeg(is_hardware_accelerated=False)

def copy_date(input_file, output_file):
    """
    Copies the modification and creation time of a file onto another.
    """
    mtime = int(input_file.stat().st_mtime)
    os.utime(output_file, (mtime, mtime))
    ctime = int(input_file.stat().st_ctime)
    set_created_time(output_file, ctime)

import pywintypes, win32file, win32con
def set_created_time(file, timestamp):
    # Enormous hack to set the creation time of a file on Windows.
    # From https://stackoverflow.com/a/4996407/252218
    wintime = pywintypes.Time(timestamp)
    winfile = win32file.CreateFile(
        str(file.absolute()), win32con.GENERIC_WRITE,
        win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE | win32con.FILE_SHARE_DELETE,
        None, win32con.OPEN_EXISTING,
        win32con.FILE_ATTRIBUTE_NORMAL, None)
    win32file.SetFileTime(winfile, wintime, None, None)
    winfile.close()

class ShrinkingError(Exception): pass

if __name__ == '__main__':
    import sys
    if len(sys.argv) != 3:
        print('Usage: python media_shrinker.py source_dir destination_dir')
        exit()
    base_source, base_destination = map(Path, sys.argv[1:])
    assert not base_destination.is_relative_to(base_source)

    for input_file in base_source.glob('**/*'):
        if input_file.is_dir(): continue
        if input_file.stat().st_size == 0: continue

        # Find an equivalent path inside base_destination.
        output_file = base_destination / input_file.relative_to(base_source)
        if output_file.exists(): continue

        print(output_file)

        # Create parent folders if necessary.
        output_file.parent.mkdir(parents=True, exist_ok=True)
        # Save converted file to .tmp first, so that if the process is
        # interrupted we'll try the conversion again instead of leaving a
        # corrupted file behind.
        output_file_temp = Path(f'{output_file}.tmp')
        broad_types = [type.split('/')[0] for type in mimetypes.guess_type(input_file) if type]
        try:
            if 'video' in broad_types:
                shrink_video(input_file, output_file_temp)
                print('\tconverted video')
            elif 'image' in broad_types:
                shrink_image(input_file, output_file_temp)
                print('\tconverted image')
            else:
                raise ShrinkingError()

            # The file has been converted, but it's not worth using it if it's
            # not sufficiently smaller than the original.
            original_size = input_file.stat().st_size
            new_size = output_file_temp.stat().st_size
            if new_size > original_size * 0.9:
                print('\tnew file is too large, discarding')
                # Too big, shrinking process did not work correctly.
                raise ShrinkingError()
        except (ShrinkingError, CalledProcessError):
            # We either failed or refused to convert the file. Make a simple
            # copy instead.
            copy2(input_file, output_file_temp)
            print('\tcopied file without alterations')

        # Success! Make temp file permanent.
        os.rename(output_file_temp, output_file)

        # Make sure that modification and creation times are copied.
        copy_date(input_file, output_file)