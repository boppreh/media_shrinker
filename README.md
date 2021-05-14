# media_shrinker
Personal script for shrinking images and videos

```
python media_shrinker.py source destination
```

E.g.
```
python media_shrinker.py "/d/media/camera" "/d/sync/send - smaller_media"
```

This script is meant to convert media files from a source directory into
roughly equivalent but smaller files in the destination direction.

Uses ImageMagick to convert images and ffmpeg for videos, converting them down
to Full HD resolution. Care is taken to copy the creation and modification times
of the original files. Non-media files are copied as-is.

This script was written as a hacky way of keeping all my photos and videos in my
storage-challenged phone, without relying on Google Photos or other cloud
services.
