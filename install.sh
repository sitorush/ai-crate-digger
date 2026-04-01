#!/bin/bash
# ai-crate-digger - One-Click Installer

set -e

echo "╔════════════════════════════════════════╗"
echo "║   ai-crate-digger - Easy Installer    ║"
echo "╚════════════════════════════════════════╝"
echo ""

# Check Python version
if ! command -v python3.11 &> /dev/null; then
    echo "❌ Python 3.11 is required but not installed."
    echo ""
    echo "Please install Python 3.11 from:"
    echo "https://www.python.org/downloads/"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

echo "✓ Python 3.11 found"
echo ""

# Install location
INSTALL_DIR="$HOME/ai-crate-digger"
echo "Installing to: $INSTALL_DIR"
echo ""

# Create install directory
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Copy files
echo "📦 Copying files..."
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cp -r "$SCRIPT_DIR"/* "$INSTALL_DIR/" 2>/dev/null || true

# Create virtual environment
echo "🔧 Setting up Python environment..."
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
echo "📚 Installing dependencies (this may take 5-10 minutes)..."
pip install --upgrade pip > /dev/null 2>&1
pip install -e . > /dev/null 2>&1

# Create launcher script
echo "🚀 Creating launcher..."
cat > "$HOME/Desktop/ai-crate-digger.command" << 'LAUNCHER'
#!/bin/bash
cd "$HOME/ai-crate-digger"
source venv/bin/activate

# Simple menu
while true; do
    clear
    echo "╔════════════════════════════════════════╗"
    echo "║         ai-crate-digger                ║"
    echo "╚════════════════════════════════════════╝"
    echo ""
    echo "1. Scan Music Library"
    echo "2. Search Tracks"
    echo "3. Generate Playlist"
    echo "4. View Stats"
    echo "5. Quit"
    echo ""
    read -p "Choose an option (1-5): " choice

    case $choice in
        1)
            echo ""
            read -p "Enter music folder path (or drag folder here): " music_path
            music_path="${music_path// /\\ }"  # Handle spaces
            crate scan "$music_path"
            read -p "Press Enter to continue..."
            ;;
        2)
            echo ""
            read -p "Search for (e.g., 'techno', 'artist:deadmau5'): " query
            crate search "$query"
            read -p "Press Enter to continue..."
            ;;
        3)
            echo ""
            read -p "Genre/tags (e.g., 'techno house'): " tags
            read -p "Duration in minutes (e.g., 60): " duration
            read -p "Output file (e.g., ~/Desktop/playlist.m3u): " output
            crate playlist --tags "$tags" --duration "$duration" -o "$output"
            echo "✓ Playlist saved to: $output"
            read -p "Press Enter to continue..."
            ;;
        4)
            crate stats
            read -p "Press Enter to continue..."
            ;;
        5)
            echo "Goodbye!"
            exit 0
            ;;
        *)
            echo "Invalid option"
            sleep 1
            ;;
    esac
done
LAUNCHER

chmod +x "$HOME/Desktop/ai-crate-digger.command"

echo ""
echo "✅ Installation Complete!"
echo ""
echo "╔════════════════════════════════════════╗"
echo "║  🎵 ai-crate-digger is ready to use! ║"
echo "╚════════════════════════════════════════╝"
echo ""
echo "Look for 'ai-crate-digger' icon on your Desktop"
echo "Double-click it to start!"
echo ""
read -p "Press Enter to finish..."
