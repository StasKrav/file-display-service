#!/bin/bash

# File Manager with CD-on-exit functionality
# Usage: Add this function to your ~/.bashrc or ~/.zshrc
# Then use: fm    (normal file manager)
#       or: fmc   (file manager with cd-on-exit)

fm() {
    # Normal file manager without cd-on-exit
    python3 /home/stas/Music/filemanager.py
}

fmc() {
    # File manager with cd-on-exit functionality
    local temp_file
    local exit_code
    
    # Run the file manager with --cd flag and capture the temp file path
    temp_file=$(python3 /home/stas/Music/filemanager.py --cd 2>/dev/null)
    exit_code=$?
    
    # If file manager ran successfully and temp file exists
    if [[ $exit_code -eq 0 && -f "$temp_file" ]]; then
        local target_dir
        target_dir=$(cat "$temp_file" 2>/dev/null)
        
        # Clean up temp file
        rm -f "$temp_file" 2>/dev/null
        
        # Change to the target directory if it exists
        if [[ -n "$target_dir" && -d "$target_dir" ]]; then
            cd "$target_dir"
            echo "Changed to: $target_dir"
        fi
    else
        # Clean up temp file on failure
        [[ -n "$temp_file" ]] && rm -f "$temp_file" 2>/dev/null
    fi
}

# For convenience, you can also create an alias
alias ranger='fmc'  # Replace ranger-like functionality

echo "File manager functions loaded:"
echo "  fm    - Normal file manager"
echo "  fmc   - File manager with cd-on-exit"
echo ""
echo "To enable permanently, add this to your ~/.bashrc or ~/.zshrc:"
echo "source /home/stas/Music/fm_wrapper.sh"