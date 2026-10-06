#!/bin/bash
# verify-wallpaper-setup.sh — confirm all Smart Video Wallpaper Reborn config steps are live
# Run: bash ~/hermes-skills/smart-video-wallpaper-reborn/scripts/verify-wallpaper-setup.sh

echo "=== Smart Video Wallpaper Reborn — Setup Verification ==="

echo "1. QT_MEDIA_BACKEND:"
echo "   $QT_MEDIA_BACKEND"

echo ""
echo "2. plasma-wallpaper.conf videoFile:"
VIDEOFILE=$(kreadconfig6 --file ~/.config/plasma-workspace/env/plasma-wallpaper.conf --group WallpaperSmartVideo --key videoFile 2>/dev/null || echo 'MISSING')
echo "   $VIDEOFILE"

echo ""
echo "3. plasma-wallpaper.conf videoPath:"
VIDEOPATH=$(kreadconfig6 --file ~/.config/plasma-workspace/env/plasma-wallpaper.conf --group WallpaperSmartVideo --key videoPath 2>/dev/null || echo 'MISSING')
echo "   $VIDEOPATH"

echo ""
echo "4. KScreenSaver WallpaperPlugin:"
PLUGIN=$(kreadconfig6 --group KScreenSaver --key WallpaperPlugin 2>/dev/null || echo 'MISSING')
echo "   $PLUGIN"

echo ""
echo "5. KScreenSaver WallpaperMode:"
MODE=$(kreadconfig6 --group KScreenSaver --key WallpaperMode 2>/dev/null || echo 'MISSING')
echo "   $MODE"

echo ""
echo "6. qt-media-backend.sh exists + executable:"
if [ -x ~/.config/plasma-workspace/env/qt-media-backend.sh ]; then
  echo "   YES — $(cat ~/.config/plasma-workspace/env/qt-media-backend.sh)"
else
  echo "   NO — not found or not executable"
fi

echo ""
echo "=== End of verification ==="