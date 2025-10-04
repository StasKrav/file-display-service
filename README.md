# Terminal File Manager

A powerful, dependency-free terminal-based file manager written in Python using only the standard library. Features dual-panel mode, multi-selection, search, filtering, and quick file preview.

![Terminal File Manager](https://img.shields.io/badge/Python-3.6+-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Linux-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## 🎯 Features

### Core Functionality
- **🖥️ Single & Dual Panel Mode** - Norton Commander-style interface
- **📁 Full File Operations** - Copy, move, delete, rename, create files/directories
- **⭐ Multi-Selection** - Select multiple files with visual indicators
- **🔍 Search & Filter** - Find files by name or filter by extension
- **👁️ Quick Preview** - View text files without opening external editor
- **🎨 Colored Interface** - Different colors for files, directories, executables
- **📋 Smart Clipboard** - Copy/cut multiple files, paste anywhere
- **🚪 CD-on-Exit** - Change terminal directory when exiting

### Advanced Features
- **Navigation with arrow keys** or Vim-style keys (hjkl)
- **Hidden files toggle**
- **Safe deletion** with confirmation dialogs
- **Real-time file information** (size, date, permissions)
- **Error handling** with user-friendly messages
- **ESC support** in all dialogs

## 🚀 Quick Start

### Requirements
- Python 3.6+
- Linux terminal with curses support
- No additional dependencies required!

### Installation

1. **Download the file manager:**
   ```bash
   wget https://raw.githubusercontent.com/your-repo/filemanager.py
   # or just copy the filemanager.py file
   ```

2. **Make it executable:**
   ```bash
   chmod +x filemanager.py
   ```

3. **Run it:**
   ```bash
   ./filemanager.py
   ```

### CD-on-Exit Setup (Optional)

To enable changing terminal directory when exiting:

1. **Source the wrapper:**
   ```bash
   source fm_wrapper.sh
   ```

2. **Add to your shell config:**
   ```bash
   # For permanent setup, add to ~/.bashrc or ~/.zshrc:
   echo "source /path/to/fm_wrapper.sh" >> ~/.zshrc
   ```

3. **Use the enhanced commands:**
   ```bash
   fm    # Normal file manager
   fmc   # File manager with cd-on-exit
   ```

## ⌨️ Keyboard Shortcuts

### Navigation
| Key | Action |
|-----|--------|
| `↑` / `k` | Move up |
| `↓` / `j` | Move down |
| `←` / `h` | Go to parent directory |
| `→` / `l` | Enter directory / Open file |
| `Enter` | Enter directory / Open file |
| `Backspace` | Go to parent directory |

### File Operations
| Key | Action |
|-----|--------|
| `c` | Copy file(s) |
| `x` | Cut file(s) |
| `v` | Paste file(s) |
| `d` | Delete file(s)/directory(ies) |
| `r` | Rename file |
| `o` | Open file with default program |

### Multi-Selection
| Key | Action |
|-----|--------|
| `Space` | Toggle file selection |
| `a` | Select all files |
| `A` | Clear all selections |

### Search & Filter
| Key | Action |
|-----|--------|
| `s` | Search files by name |
| `f` | Filter by file extension |
| `\` | Clear search/filter |
| `p` | Preview text file |

### View Options
| Key | Action |
|-----|--------|
| `.` | Show/hide hidden files |
| `F5` | Refresh |

### Panel Mode
| Key | Action |
|-----|--------|
| `F2` | Toggle dual panel mode |
| `Tab` | Switch between panels |

### Create New
| Key | Action |
|-----|--------|
| `n` | Create new file |
| `m` | Create new directory |

### Other
| Key | Action |
|-----|--------|
| `?` | Show help |
| `q` | Quit |
| `ESC` | Cancel dialog / Quit |

## 🎮 Usage Examples

### Basic File Operations
```bash
# Navigate to a directory
# Use arrow keys or hjkl to move around
# Press Enter or → to enter directories
# Press ← or Backspace to go up

# Copy files
# Select files with Space, press 'c' to copy
# Navigate to destination, press 'v' to paste

# Multi-select operations
# Press Space on multiple files (see * markers)
# Use any operation (copy, delete, etc.) on all selected
```

### Search and Filter
```bash
# Search for files containing "config"
# Press 's', type "config", press Enter

# Filter Python files only
# Press 'f', type ".py", press Enter

# Clear search/filter
# Press '\' or ESC
```

### Dual Panel Mode
```bash
# Enable dual panel mode
# Press F2 to split screen

# Switch between panels
# Press Tab to move between left/right panels

# Copy between panels
# Select files in one panel, press 'c'
# Switch to other panel with Tab, press 'v'
```

## 🎨 Interface

### Single Panel Mode
```
┌─ File Manager - /home/user/documents ──────────────────┐
│  * file1.txt      1.2K  2023-10-04 15:30            │
│    file2.py       3.4K  2023-10-04 14:20            │
│    folder/        <DIR> 2023-10-03 16:45            │
│    image.jpg      2.1M  2023-10-02 12:15            │
├─────────────────────────────────────────────────────────┤
│ Files: 3 | Selected: 1 files | s=Search f=Filter     │
└─────────────────────────────────────────────────────────┘
```

### Dual Panel Mode
```
┌─ L: /home/user/docs ──┬─ R: /home/user/music ─────┐
│  * file1.txt    1.2K  │    song1.mp3      4.5M   │
│    file2.py     3.4K  │  * song2.mp3      3.2M   │
│    folder/      <DIR> │    album/         <DIR>   │
├───────────────────────┼───────────────────────────┤
│ Panel 1 | Files: 3 | Selected: 1 files | ? help │
└─────────────────────────────────────────────────────┘
```

## 🔧 Configuration

The file manager works out of the box with sensible defaults. However, you can modify the source code to customize:

- **Colors**: Modify the `curses.init_pair()` calls in `__init__`
- **Key bindings**: Change the key mappings in the `run()` method
- **File size limits**: Adjust preview limits in `quick_preview()`
- **Display format**: Modify the `draw_file_list()` method

## 🐛 Troubleshooting

### Common Issues

**Q: Arrow keys don't work**
```bash
# Make sure your terminal supports curses
# Try running: python3 -c "import curses; print('OK')"
```

**Q: Colors don't appear**
```bash
# Check if your terminal supports colors
# Try: echo $TERM
# Should show something like 'xterm-256color'
```

**Q: Permission denied errors**
```bash
# Make sure the script is executable
chmod +x filemanager.py

# Check file permissions in the directories you're browsing
```

**Q: ESC doesn't work in dialogs**
```bash
# This should be fixed in the latest version
# Make sure you're using the updated filemanager.py
```

### Debug Mode

For debugging, you can run with Python directly:
```bash
python3 filemanager.py
```

Any errors will be displayed when the program exits.

## 🤝 Contributing

This is a single-file Python application that's easy to modify and extend. Some ideas for contributions:

- **Archive support** (zip, tar.gz extraction/creation)
- **Sorting options** (by name, size, date)
- **Bookmarks system**
- **File associations**
- **Progress bars** for large operations
- **Network support** (FTP, SSH)

## 📝 License

MIT License - feel free to use, modify, and distribute.

## 🙏 Acknowledgments

Inspired by classic file managers like:
- Norton Commander
- Midnight Commander
- ranger

Built with love using only Python standard library! 🐍

---

**Enjoy your new terminal file manager!** ⭐

For issues, suggestions, or contributions, please open an issue or submit a pull request.