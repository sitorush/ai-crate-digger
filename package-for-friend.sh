#!/bin/bash
# Package ai-crate-digger for sharing with non-technical friend
# NOTE: This script is for sharing the source directory directly.
# For most users, just share the GitHub URL instead:
# https://github.com/sitorush/ai-crate-digger

echo "📦 Packaging ai-crate-digger for sharing..."

# Create clean package
PACKAGE_NAME="ai-crate-digger-easy-install"
rm -rf "/tmp/$PACKAGE_NAME" "/tmp/$PACKAGE_NAME.zip"
mkdir -p "/tmp/$PACKAGE_NAME"

# Copy only source files
cp -r src "/tmp/$PACKAGE_NAME/"
cp -r tests "/tmp/$PACKAGE_NAME/"
cp -r docs "/tmp/$PACKAGE_NAME/"
cp pyproject.toml "/tmp/$PACKAGE_NAME/"
cp README.md "/tmp/$PACKAGE_NAME/"
cp START_HERE.md "/tmp/$PACKAGE_NAME/"
cp install.sh "/tmp/$PACKAGE_NAME/"
cp .gitignore "/tmp/$PACKAGE_NAME/" 2>/dev/null || true

# Make installer executable
chmod +x "/tmp/$PACKAGE_NAME/install.sh"

# Create the zip
cd /tmp
zip -r "$PACKAGE_NAME.zip" "$PACKAGE_NAME" -x "*.pyc" -x "*__pycache__*" > /dev/null

# Move to Desktop
mv "$PACKAGE_NAME.zip" ~/Desktop/

# Clean up
rm -rf "/tmp/$PACKAGE_NAME"

SIZE=$(du -h ~/Desktop/$PACKAGE_NAME.zip | cut -f1)
echo ""
echo "✅ Package created: ~/Desktop/$PACKAGE_NAME.zip ($SIZE)"
echo ""
echo "📧 Share this file with your friend via:"
echo "   • AirDrop (easiest for Mac users)"
echo "   • Email (if < 25MB)"
echo "   • Google Drive / Dropbox"
echo "   • WeTransfer"
echo ""
echo "Instructions for your friend:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. Unzip ai-crate-digger-easy-install.zip"
echo "2. Open the folder and read START_HERE.md"
echo "3. Double-click install.sh"
echo "4. Wait 5-10 minutes"
echo "5. Look for 'ai-crate-digger' on Desktop"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
