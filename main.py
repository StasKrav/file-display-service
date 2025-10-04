#!/usr/bin/env python3
"""
Dependency-free Terminal File Manager
A simple TUI file manager for Linux using only Python standard library
"""

import curses
import os
import stat
import shutil
import subprocess
import time
import json
from datetime import datetime
from pathlib import Path


class FileManager:
    def __init__(self, stdscr, cd_on_exit=False, temp_file=None):
        self.stdscr = stdscr
        self.current_path = Path.cwd()
        self.selected_index = 0
        self.scroll_offset = 0
        self.files = []
        self.show_hidden = False
        self.clipboard = None
        self.clipboard_action = None  # 'copy' or 'cut'
        self.message = ""
        self.message_time = 0
        self.cd_on_exit = cd_on_exit
        self.temp_file = temp_file
        self.selected_files = set()  # Set of selected file indices
        self.multi_select_mode = False
        
        # Two-panel mode
        self.dual_panel_mode = False
        self.active_panel = 0  # 0 = left, 1 = right
        
        # Panel data - [left_panel, right_panel]
        self.panel_paths = [Path.cwd(), Path.cwd()]
        self.panel_selected_index = [0, 0]
        self.panel_scroll_offset = [0, 0]
        self.panel_files = [[], []]
        self.panel_selected_files = [set(), set()]
        
        # Search and filter functionality
        self.search_mode = False
        self.search_query = ""
        self.filter_mode = False
        self.filter_extension = ""
        self.original_files = []  # Store unfiltered files
        
        # Initialize colors
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_BLUE, -1)      # Directories
        curses.init_pair(2, curses.COLOR_GREEN, -1)     # Executables
        curses.init_pair(3, curses.COLOR_BLUE, -1)    # Selected item
        curses.init_pair(4, curses.COLOR_RED, -1)       # Error messages
        curses.init_pair(5, curses.COLOR_MAGENTA, -1)      # Status bar
        curses.init_pair(6, curses.COLOR_MAGENTA, -1)   # Special files
        
        # Hide cursor
        curses.curs_set(0)
        
        # Enable keypad for arrow keys
        stdscr.keypad(True)
        
        # Initialize panel data
        self.sync_to_panels()
        self.refresh_files()

    def sync_to_panels(self):
        """Sync current state to panel data"""
        self.panel_paths[self.active_panel] = self.current_path
        self.panel_selected_index[self.active_panel] = self.selected_index
        self.panel_scroll_offset[self.active_panel] = self.scroll_offset
        self.panel_selected_files[self.active_panel] = self.selected_files.copy()

    def sync_from_panels(self):
        """Sync panel data to current state"""
        self.current_path = self.panel_paths[self.active_panel]
        self.selected_index = self.panel_selected_index[self.active_panel]
        self.scroll_offset = self.panel_scroll_offset[self.active_panel]
        self.selected_files = self.panel_selected_files[self.active_panel].copy()
        if self.dual_panel_mode:
            self.files = self.panel_files[self.active_panel]

    def switch_panel(self):
        """Switch active panel in dual-panel mode"""
        if self.dual_panel_mode:
            # Save current panel state
            self.panel_paths[self.active_panel] = self.current_path
            self.panel_selected_index[self.active_panel] = self.selected_index
            self.panel_scroll_offset[self.active_panel] = self.scroll_offset
            self.panel_selected_files[self.active_panel] = self.selected_files.copy()
            
            # Switch to other panel
            self.active_panel = 1 - self.active_panel
            
            # Load other panel state
            self.current_path = self.panel_paths[self.active_panel]
            self.selected_index = self.panel_selected_index[self.active_panel]
            self.scroll_offset = self.panel_scroll_offset[self.active_panel]
            self.selected_files = self.panel_selected_files[self.active_panel].copy()
            self.files = self.panel_files[self.active_panel]

    def toggle_dual_panel(self):
        """Toggle between single and dual panel modes"""
        if not self.dual_panel_mode:
            # Entering dual panel mode
            self.dual_panel_mode = True
            
            # Initialize both panels with current state
            self.sync_to_panels()
            
            # Initialize the other panel with the same directory
            other_panel = 1 - self.active_panel
            self.panel_paths[other_panel] = self.current_path
            self.panel_selected_index[other_panel] = 0
            self.panel_scroll_offset[other_panel] = 0
            self.panel_selected_files[other_panel] = set()
            
            # Refresh both panels
            for i in range(2):
                self.refresh_panel_files(i)
            
            # Update current files to active panel
            self.files = self.panel_files[self.active_panel]
            self.show_message("Dual panel mode ON - TAB to switch panels")
        else:
            # Exiting dual panel mode
            self.dual_panel_mode = False
            # Keep current active panel state
            self.sync_from_panels()
            self.show_message("Single panel mode")
        
        # Always refresh after mode change
        if not self.dual_panel_mode:
            self.refresh_files()

    def refresh_panel_files(self, panel_idx):
        """Refresh files for a specific panel"""
        try:
            path = self.panel_paths[panel_idx]
            files = []
            
            # Don't add parent directory entry - use navigation instead
            
            # Get all files and directories
            entries = []
            try:
                for entry in path.iterdir():
                    if not self.show_hidden and entry.name.startswith('.'):
                        continue
                    
                    try:
                        stat_info = entry.stat()
                        entries.append((
                            entry.name,
                            entry.is_dir(),
                            stat_info.st_size,
                            stat_info.st_mode,
                            stat_info.st_mtime
                        ))
                    except (OSError, PermissionError):
                        entries.append((entry.name, entry.is_dir(), 0, 0, 0))
                        
            except PermissionError:
                # Keep empty file list for inaccessible directories
                pass
            
            # Sort: directories first, then files, both alphabetically
            entries.sort(key=lambda x: (not x[1], x[0].lower()))
            files.extend(entries)
            
            self.panel_files[panel_idx] = files
            
            # Adjust selected index if necessary
            if self.panel_selected_index[panel_idx] >= len(files):
                self.panel_selected_index[panel_idx] = max(0, len(files) - 1)
            
            # Clear multi-selection for this panel
            self.panel_selected_files[panel_idx].clear()
                
        except Exception:
            self.panel_files[panel_idx] = []

    def refresh_files(self):
        """Refresh the file list for current directory"""
        if self.dual_panel_mode:
            # In dual panel mode, refresh both panels
            self.refresh_panel_files(0)
            self.refresh_panel_files(1)
            # Update current files to active panel
            self.files = self.panel_files[self.active_panel]
        else:
            # Single panel mode - original logic
            try:
                self.files = []
                
            # Don't add parent directory entry - use navigation instead
                
                # Get all files and directories
                entries = []
                try:
                    for entry in self.current_path.iterdir():
                        if not self.show_hidden and entry.name.startswith('.'):
                            continue
                        
                        try:
                            stat_info = entry.stat()
                            entries.append((
                                entry.name,
                                entry.is_dir(),
                                stat_info.st_size,
                                stat_info.st_mode,
                                stat_info.st_mtime
                            ))
                        except (OSError, PermissionError):
                            # Add entry even if we can't stat it
                            entries.append((entry.name, entry.is_dir(), 0, 0, 0))
                            
                except PermissionError:
                    self.show_message("Permission denied", error=True)
                    return
                
                # Sort: directories first, then files, both alphabetically
                entries.sort(key=lambda x: (not x[1], x[0].lower()))
                self.files.extend(entries)
                
                # Adjust selected index if necessary
                if self.selected_index >= len(self.files):
                    self.selected_index = max(0, len(self.files) - 1)
                
                # Clear multi-selection when directory changes
                self.selected_files.clear()
                
                # Clear search/filter when changing directories
                if self.search_mode or self.filter_mode:
                    self.original_files = []
                    self.search_mode = False
                    self.filter_mode = False
                    self.search_query = ""
                    self.filter_extension = ""
                    
            except Exception as e:
                self.show_message(f"Error reading directory: {e}", error=True)

    def get_file_type_color(self, filename, is_dir, mode):
        """Get color pair for file type"""
        if filename == '..':
            return curses.color_pair(1)
        if is_dir:
            return curses.color_pair(1)
        elif mode and stat.S_ISFIFO(mode):
            return curses.color_pair(6)
        elif mode and stat.S_ISLNK(mode):
            return curses.color_pair(6)
        elif mode and (mode & stat.S_IEXEC):
            return curses.color_pair(2)
        else:
            return curses.A_NORMAL

    def format_size(self, size):
        """Format file size in human readable format"""
        if size == 0:
            return "0"
        
        units = ['B', 'K', 'M', 'G', 'T']
        unit_index = 0
        size_float = float(size)
        
        while size_float >= 1024 and unit_index < len(units) - 1:
            size_float /= 1024
            unit_index += 1
        
        if unit_index == 0:
            return f"{int(size_float)}"
        else:
            return f"{size_float:.1f}{units[unit_index]}"

    def format_date(self, timestamp):
        """Format timestamp to readable date"""
        if timestamp == 0:
            return "Unknown"
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")

    def draw_screen(self):
        """Draw the main screen"""
        self.stdscr.clear()
        height, width = self.stdscr.getmaxyx()
        
        # Clear any old messages after 3 seconds
        if self.message and time.time() - self.message_time > 3:
            self.message = ""
        
        if self.dual_panel_mode:
            self.draw_dual_panel(height, width)
        else:
            self.draw_single_panel(height, width)
        
        self.stdscr.refresh()

    def draw_single_panel(self, height, width):
        """Draw single panel mode"""
        # Draw title bar
        title = f"File Manager - {self.current_path}"
        try:
            self.stdscr.addstr(0, 0, title[:width-1], curses.color_pair(5) | curses.A_BOLD)
        except curses.error:
            pass
        
        self.draw_file_list(0, 1, height - 2, width, self.files, self.selected_index, self.selected_files, self.scroll_offset)
        self.draw_status_bar(height, width)
        self.draw_message_bar(height, width)

    def draw_dual_panel(self, height, width):
        """Draw dual panel mode"""
        panel_width = width // 2
        
        # Draw title bars for both panels
        left_title = f"L: {self.panel_paths[0]}"
        right_title = f"R: {self.panel_paths[1]}"
        
        try:
            # Left panel title
            left_attr = curses.color_pair(5) | curses.A_BOLD
            if self.active_panel == 0:
                left_attr |= curses.A_REVERSE
            self.stdscr.addstr(0, 0, left_title[:panel_width-1], left_attr)
            
            # Right panel title  
            right_attr = curses.color_pair(5) | curses.A_BOLD
            if self.active_panel == 1:
                right_attr |= curses.A_REVERSE
            self.stdscr.addstr(0, panel_width, right_title[:panel_width-1], right_attr)
            
            # Draw separator line
            for y in range(height - 2):
                try:
                    self.stdscr.addstr(y, panel_width - 1, "|", curses.color_pair(5))
                except curses.error:
                    pass
                    
        except curses.error:
            pass
        
        # Draw file lists for both panels
        self.draw_file_list(0, 1, height - 2, panel_width - 1, 
                           self.panel_files[0], 
                           self.panel_selected_index[0] if self.active_panel == 0 else -1,
                           self.panel_selected_files[0],  # Always show selections
                           self.panel_scroll_offset[0])
                           
        self.draw_file_list(panel_width, 1, height - 2, panel_width, 
                           self.panel_files[1], 
                           self.panel_selected_index[1] if self.active_panel == 1 else -1,
                           self.panel_selected_files[1],  # Always show selections
                           self.panel_scroll_offset[1])
        
        self.draw_status_bar(height, width, dual_panel=True)
        self.draw_message_bar(height, width)

    def draw_file_list(self, x_offset, y_start, height, width, files, selected_index, selected_files, scroll_offset):
        """Draw file list for a panel"""
        start_idx = scroll_offset
        end_idx = min(len(files), start_idx + height)
        
        for i in range(start_idx, end_idx):
            y_pos = i - start_idx + y_start
            if y_pos >= y_start + height:
                break
                
            file_info = files[i]
            filename = file_info[0]
            
            # Highlight selected file and multi-selected files
            attr = curses.A_NORMAL
            if i == selected_index:
                attr = curses.color_pair(3) | curses.A_REVERSE
            elif i in selected_files:
                attr = curses.color_pair(3) | curses.A_BOLD
            else:
                if len(file_info) > 1:
                    attr = self.get_file_type_color(filename, file_info[1], 
                                                   file_info[3] if len(file_info) > 3 else 0)
            
            # Format file info
            marker = "* " if i in selected_files else "  "
            if len(file_info) > 1:
                is_dir = file_info[1]
                size = file_info[2] if len(file_info) > 2 else 0
                mtime = file_info[4] if len(file_info) > 4 else 0
                
                if is_dir:
                    size_str = "<DIR>"
                else:
                    size_str = self.format_size(size)
                
                date_str = self.format_date(mtime)
                
                # Truncate filename if too long
                max_name_len = width - 32  # Account for marker
                if len(filename) > max_name_len:
                    display_name = filename[:max_name_len-3] + "..."
                else:
                    display_name = filename
                
                display_line = f"{marker}{display_name:<{max_name_len}} {size_str:>8} {date_str}"
            else:
                display_line = marker + filename
            
            # Draw the line
            try:
                self.stdscr.addstr(y_pos, x_offset, display_line[:width-1], attr)
            except curses.error:
                pass

    def draw_status_bar(self, height, width, dual_panel=False):
        """Draw status bar"""
        status_y = height - 2
        if status_y <= 0:
            return
            
        # Calculate file count (no parent directory entry to exclude)
        file_count = len(self.files)
        
        if dual_panel:
            status_info = f"Panel {self.active_panel + 1} | Files: {file_count} | "
        else:
            status_info = f"Files: {file_count} | "
        
        # Show multi-selection info
        if self.selected_files:
            status_info += f"Selected: {len(self.selected_files)} files | "
        elif self.files and self.selected_index < len(self.files):
            current_file = self.files[self.selected_index][0]
            if current_file == '..':
                status_info += f"Current: [Parent Dir] | "
            else:
                status_info += f"Current: {current_file} | "
        
        status_info += f"Hidden: {'ON' if self.show_hidden else 'OFF'} | "
        
        # Show active search/filter
        if self.search_mode and self.search_query:
            status_info += f"Search: {self.search_query} | "
        elif self.filter_mode and self.filter_extension:
            status_info += f"Filter: {self.filter_extension} | "
        
        if dual_panel:
            status_info += "s=Search f=Filter | ? for help"
        else:
            status_info += "F2=Dual | s=Search f=Filter | ? for help"
        
        try:
            self.stdscr.addstr(status_y, 0, status_info[:width-1], curses.color_pair(5))
        except curses.error:
            pass

    def draw_message_bar(self, height, width):
        """Draw message bar"""
        if self.message:
            msg_y = height - 1
            if msg_y > 0:
                attr = curses.color_pair(4) if self.message.startswith("Error") else curses.A_NORMAL
                try:
                    self.stdscr.addstr(msg_y, 0, self.message[:width-1], attr)
                except curses.error:
                    pass

    def show_message(self, message, error=False):
        """Show a message to the user"""
        self.message = message
        self.message_time = time.time()

    def adjust_scroll(self):
        """Adjust scroll offset to keep selected item visible"""
        height, width = self.stdscr.getmaxyx()
        visible_height = height - 3
        
        if self.selected_index < self.scroll_offset:
            self.scroll_offset = self.selected_index
        elif self.selected_index >= self.scroll_offset + visible_height:
            self.scroll_offset = self.selected_index - visible_height + 1
        
        # Sync scroll offset to panel data in dual-panel mode
        if self.dual_panel_mode:
            self.panel_scroll_offset[self.active_panel] = self.scroll_offset

    def navigate_up(self):
        """Move selection up"""
        if self.selected_index > 0:
            self.selected_index -= 1
            if self.dual_panel_mode:
                self.panel_selected_index[self.active_panel] = self.selected_index
            self.adjust_scroll()

    def navigate_down(self):
        """Move selection down"""
        if self.selected_index < len(self.files) - 1:
            self.selected_index += 1
            if self.dual_panel_mode:
                self.panel_selected_index[self.active_panel] = self.selected_index
            self.adjust_scroll()

    def navigate_left(self):
        """Navigate to parent directory (left arrow)"""
        if self.dual_panel_mode:
            self.sync_to_panels()
        
        if self.current_path != Path('/'):
            self.current_path = self.current_path.parent
            self.selected_index = 0
            self.scroll_offset = 0
            
        if self.dual_panel_mode:
            self.panel_paths[self.active_panel] = self.current_path
            self.panel_selected_index[self.active_panel] = 0
            self.panel_scroll_offset[self.active_panel] = 0
        
        self.refresh_files()

    def navigate_right(self):
        """Enter directory or open file (right arrow)"""
        if not self.files:
            return
        
        if self.dual_panel_mode:
            self.sync_to_panels()
        
        selected_file = self.files[self.selected_index]
        filename = selected_file[0]
        
        if len(selected_file) > 1 and selected_file[1]:  # is_dir
            # Enter directory
            new_path = self.current_path / filename
            try:
                # Test if we can access the directory
                list(new_path.iterdir())
                self.current_path = new_path
                self.selected_index = 0
                self.scroll_offset = 0
                
                if self.dual_panel_mode:
                    self.panel_paths[self.active_panel] = self.current_path
                    self.panel_selected_index[self.active_panel] = 0
                    self.panel_scroll_offset[self.active_panel] = 0
                
                self.refresh_files()
            except PermissionError:
                self.show_message("Permission denied", error=True)
                return
        else:
            # Try to open file with default program
            self.open_file()

    def enter_directory(self):
        """Enter selected directory or go up"""
        if not self.files:
            return
        
        selected_file = self.files[self.selected_index]
        filename = selected_file[0]
        
        if len(selected_file) > 1 and selected_file[1]:  # is_dir
            # Enter directory
            self.navigate_right()
        else:
            # Try to open file with default program
            self.open_file()

    def open_file(self):
        """Open selected file with default program"""
        if not self.files or self.selected_index >= len(self.files):
            return
        
        selected_file = self.files[self.selected_index]
        filename = selected_file[0]
        
        if len(selected_file) > 1 and selected_file[1]:
            return  # Skip directories
        
        filepath = self.current_path / filename
        try:
            subprocess.run(['xdg-open', str(filepath)], check=False, 
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.show_message(f"Opening {filename}...")
        except Exception as e:
            self.show_message(f"Error opening file: {e}", error=True)

    def delete_file(self):
        """Delete selected file(s) or directory(ies)"""
        files_to_delete = []
        
        if self.selected_files:
            # Multi-selection delete
            for idx in self.selected_files:
                if idx < len(self.files):
                    filename = self.files[idx][0]
                    files_to_delete.append((idx, filename, self.current_path / filename))
        else:
            # Single file delete
            if not self.files or self.selected_index >= len(self.files):
                return
            
            selected_file = self.files[self.selected_index]
            filename = selected_file[0]
            
            files_to_delete.append((self.selected_index, filename, self.current_path / filename))
        
        if not files_to_delete:
            return
        
        # Save current settings and disable nodelay for confirmation
        self.stdscr.nodelay(False)
        self.stdscr.timeout(-1)
        
        # Ask for confirmation
        self.stdscr.clear()
        height, width = self.stdscr.getmaxyx()
        
        # Create confirmation prompt
        if len(files_to_delete) == 1:
            _, filename, filepath = files_to_delete[0]
            is_dir = filepath.is_dir()
            file_type = "directory" if is_dir else "file"
            prompt1 = f"Delete {file_type}: '{filename}'?"
        else:
            prompt1 = f"Delete {len(files_to_delete)} selected files/directories?"
        
        prompt2 = "Press 'y' to confirm, any other key to cancel"
        
        try:
            # Center the prompts
            y_pos = height // 2 - 1
            x_pos1 = max(0, (width - len(prompt1)) // 2)
            x_pos2 = max(0, (width - len(prompt2)) // 2)
            
            self.stdscr.addstr(y_pos, x_pos1, prompt1, curses.A_BOLD | curses.color_pair(4))
            self.stdscr.addstr(y_pos + 2, x_pos2, prompt2)
            
        except curses.error:
            # Fallback if centering fails
            self.stdscr.addstr(height//2, 0, prompt1[:width-1], curses.A_BOLD | curses.color_pair(4))
            self.stdscr.addstr(height//2 + 2, 0, prompt2[:width-1])
        
        self.stdscr.refresh()
        
        # Get confirmation
        key = self.stdscr.getch()
        
        # Restore settings
        self.stdscr.nodelay(True)
        self.stdscr.timeout(100)
        
        if key in [ord('y'), ord('Y')]:
            deleted_count = 0
            errors = []
            
            # Check for non-empty directories first
            non_empty_dirs = []
            for _, filename, filepath in files_to_delete:
                if filepath.is_dir() and any(filepath.iterdir()):
                    non_empty_dirs.append(filename)
            
            # Ask for additional confirmation if there are non-empty directories
            if non_empty_dirs:
                self.stdscr.clear()
                if len(non_empty_dirs) == 1:
                    warning = f"Directory '{non_empty_dirs[0]}' is not empty!"
                else:
                    warning = f"{len(non_empty_dirs)} directories are not empty!"
                confirm = "Press 'y' again to delete recursively"
                
                try:
                    y_pos = height // 2 - 1
                    x_pos1 = max(0, (width - len(warning)) // 2)
                    x_pos2 = max(0, (width - len(confirm)) // 2)
                    
                    self.stdscr.addstr(y_pos, x_pos1, warning, curses.A_BOLD | curses.color_pair(4))
                    self.stdscr.addstr(y_pos + 2, x_pos2, confirm)
                except curses.error:
                    self.stdscr.addstr(height//2, 0, warning[:width-1], curses.A_BOLD | curses.color_pair(4))
                    self.stdscr.addstr(height//2 + 2, 0, confirm[:width-1])
                
                self.stdscr.refresh()
                self.stdscr.nodelay(False)
                key2 = self.stdscr.getch()
                self.stdscr.nodelay(True)
                self.stdscr.timeout(100)
                
                if key2 not in [ord('y'), ord('Y')]:
                    self.show_message("Delete cancelled")
                    return
            
            # Proceed with deletion
            for idx, filename, filepath in files_to_delete:
                try:
                    if filepath.is_dir():
                        shutil.rmtree(filepath)
                    else:
                        filepath.unlink()
                    deleted_count += 1
                    
                except PermissionError:
                    errors.append(f"{filename}: Permission denied")
                except Exception as e:
                    errors.append(f"{filename}: {str(e)}")
            
            # Clear selections after successful deletions
            self.selected_files.clear()
            
            # Show results
            if deleted_count > 0:
                self.show_message(f"Deleted {deleted_count} file(s)")
            
            if errors:
                self.show_message(f"Errors: {'; '.join(errors[:2])}" + ("..." if len(errors) > 2 else ""), error=True)
            
            # Adjust selection if we deleted the current item
            if self.selected_index >= len(self.files):
                self.selected_index = max(0, len(self.files) - 1)
            
            self.refresh_files()
                
        else:
            self.show_message("Delete cancelled")

    def copy_file(self):
        """Copy selected file(s) to clipboard"""
        if self.selected_files:
            # Multi-selection copy
            self.clipboard = []
            for idx in self.selected_files:
                if idx < len(self.files):
                    filename = self.files[idx][0]
                    self.clipboard.append(self.current_path / filename)
            self.clipboard_action = 'copy'
            count = len(self.clipboard)
            self.show_message(f"Copied {count} file(s) to clipboard")
        else:
            # Single file copy
            if not self.files or self.selected_index >= len(self.files):
                return
            
            selected_file = self.files[self.selected_index]
            filename = selected_file[0]
            
            self.clipboard = [self.current_path / filename]
            self.clipboard_action = 'copy'
            self.show_message(f"Copied {filename}")

    def cut_file(self):
        """Cut selected file(s) to clipboard"""
        if self.selected_files:
            # Multi-selection cut
            self.clipboard = []
            for idx in self.selected_files:
                if idx < len(self.files):
                    filename = self.files[idx][0]
                    self.clipboard.append(self.current_path / filename)
            self.clipboard_action = 'cut'
            count = len(self.clipboard)
            self.show_message(f"Cut {count} file(s) to clipboard")
        else:
            # Single file cut
            if not self.files or self.selected_index >= len(self.files):
                return
            
            selected_file = self.files[self.selected_index]
            filename = selected_file[0]
            
            self.clipboard = [self.current_path / filename]
            self.clipboard_action = 'cut'
            self.show_message(f"Cut {filename}")

    def paste_file(self):
        """Paste file(s) from clipboard"""
        if not self.clipboard:
            self.show_message("Nothing to paste", error=True)
            return
        
        # Handle both single file (backward compatibility) and multi-file
        sources = self.clipboard if isinstance(self.clipboard, list) else [self.clipboard]
        
        pasted_count = 0
        errors = []
        
        for source in sources:
            dest = self.current_path / source.name
            
            # Skip if destination already exists
            if dest.exists():
                errors.append(f"{source.name} already exists")
                continue
            
            try:
                if self.clipboard_action == 'copy':
                    if source.is_dir():
                        shutil.copytree(source, dest)
                    else:
                        shutil.copy2(source, dest)
                elif self.clipboard_action == 'cut':
                    shutil.move(str(source), str(dest))
                
                pasted_count += 1
                
            except Exception as e:
                errors.append(f"{source.name}: {str(e)}")
        
        # Clear clipboard after cut operation
        if self.clipboard_action == 'cut' and pasted_count > 0:
            self.clipboard = None
            self.clipboard_action = None
        
        # Show results
        if pasted_count > 0:
            action = "Copied" if self.clipboard_action == 'copy' else "Moved"
            self.show_message(f"{action} {pasted_count} file(s)")
        
        if errors:
            self.show_message(f"Errors: {'; '.join(errors[:3])}" + ("..." if len(errors) > 3 else ""), error=True)
        
        self.refresh_files()

    def rename_file(self):
        """Rename selected file"""
        if not self.files or self.selected_index >= len(self.files):
            return
        
        selected_file = self.files[self.selected_index]
        filename = selected_file[0]
        
        # Save current settings
        self.stdscr.nodelay(False)
        self.stdscr.timeout(-1)
        curses.curs_set(1)
        
        try:
            self.stdscr.clear()
            height, width = self.stdscr.getmaxyx()
            prompt = f"Rename '{filename}' to: "
            
            self.stdscr.addstr(height//2, 0, prompt, curses.A_BOLD)
            self.stdscr.addstr(height//2 + 2, 0, "Press Enter to confirm, ESC to cancel")
            self.stdscr.refresh()
            
            # Get new name with ESC support
            new_name = self.get_dialog_input(height//2, len(prompt), 50)
            
            if new_name is None:
                # User pressed ESC
                self.show_message("Rename cancelled")
            elif new_name.strip() and new_name.strip() != filename:
                new_name = new_name.strip()
                # Validate new name
                if '/' in new_name or new_name in ['.', '..']:
                    self.show_message("Invalid file name", error=True)
                else:
                    old_path = self.current_path / filename
                    new_path = self.current_path / new_name
                    
                    if new_path.exists():
                        self.show_message(f"File '{new_name}' already exists", error=True)
                    else:
                        old_path.rename(new_path)
                        self.show_message(f"Renamed '{filename}' to '{new_name}'")
                        self.refresh_files()
            else:
                self.show_message("Rename cancelled")
        
        except KeyboardInterrupt:
            self.show_message("Rename cancelled")
        except Exception as e:
            self.show_message(f"Error renaming: {e}", error=True)
        finally:
            curses.curs_set(0)
            self.stdscr.nodelay(True)
            self.stdscr.timeout(100)

    def create_directory(self):
        """Create a new directory"""
        # Save current settings
        self.stdscr.nodelay(False)
        self.stdscr.timeout(-1)
        curses.curs_set(1)
        
        try:
            self.stdscr.clear()
            height, width = self.stdscr.getmaxyx()
            prompt = "New directory name: "
            
            # Draw prompt
            self.stdscr.addstr(height//2, 0, prompt, curses.A_BOLD)
            self.stdscr.addstr(height//2 + 2, 0, "Press Enter to confirm, ESC to cancel")
            self.stdscr.refresh()
            
            # Get directory name with ESC support
            dir_name = self.get_dialog_input(height//2, len(prompt), 50)
            
            if dir_name is None:
                # User pressed ESC
                self.show_message("Directory creation cancelled")
            elif dir_name.strip():
                dir_name = dir_name.strip()
                # Validate directory name
                if '/' in dir_name or dir_name in ['.', '..']:
                    self.show_message("Invalid directory name", error=True)
                else:
                    new_dir = self.current_path / dir_name
                    if new_dir.exists():
                        self.show_message(f"Directory '{dir_name}' already exists", error=True)
                    else:
                        new_dir.mkdir()
                        self.show_message(f"Created directory '{dir_name}'")
                        self.refresh_files()
            else:
                self.show_message("Directory creation cancelled")
        
        except KeyboardInterrupt:
            self.show_message("Directory creation cancelled")
        except Exception as e:
            self.show_message(f"Error creating directory: {e}", error=True)
        finally:
            # Restore settings
            curses.curs_set(0)
            self.stdscr.nodelay(True)
            self.stdscr.timeout(100)

    def create_file(self):
        """Create a new file"""
        # Save current settings
        self.stdscr.nodelay(False)
        self.stdscr.timeout(-1)
        curses.curs_set(1)
        
        try:
            self.stdscr.clear()
            height, width = self.stdscr.getmaxyx()
            prompt = "New file name: "
            
            # Draw prompt
            self.stdscr.addstr(height//2, 0, prompt, curses.A_BOLD)
            self.stdscr.addstr(height//2 + 2, 0, "Press Enter to confirm, ESC to cancel")
            self.stdscr.refresh()
            
            # Get file name with ESC support
            file_name = self.get_dialog_input(height//2, len(prompt), 50)
            
            if file_name is None:
                # User pressed ESC
                self.show_message("File creation cancelled")
            elif file_name.strip():
                file_name = file_name.strip()
                # Validate file name
                if '/' in file_name or file_name in ['.', '..']:
                    self.show_message("Invalid file name", error=True)
                else:
                    new_file = self.current_path / file_name
                    if new_file.exists():
                        self.show_message(f"File '{file_name}' already exists", error=True)
                    else:
                        new_file.touch()
                        self.show_message(f"Created file '{file_name}'")
                        self.refresh_files()
            else:
                self.show_message("File creation cancelled")
        
        except KeyboardInterrupt:
            self.show_message("File creation cancelled")
        except Exception as e:
            self.show_message(f"Error creating file: {e}", error=True)
        finally:
            # Restore settings
            curses.curs_set(0)
            self.stdscr.nodelay(True)
            self.stdscr.timeout(100)

    def show_help(self):
        """Show help screen without flicker"""
        help_text = [
            "File Manager - Keyboard Shortcuts",
            "",
            "Navigation:",
            "  ↑ / k           Move up",
            "  ↓ / j           Move down", 
            "  ← / h           Go to parent directory",
            "  → / l           Enter directory / Open file",
            "  Enter           Enter directory / Open file",
            "  Backspace       Go to parent directory",
            "",
            "File Operations:",
            "  c               Copy file(s)",
            "  x               Cut file(s)", 
            "  v               Paste file(s)",
            "  d               Delete file(s)/directory(ies)",
            "  r               Rename file",
            "  o               Open file with default program",
            "",
            "Multi-Selection:",
            "  SPACE           Toggle file selection",
            "  a               Select all files",
            "  A               Clear all selections",
            "",
            "Search & Filter:",
            "  s               Search files by name",
            "  f               Filter by file extension",
            "  \\               Clear search/filter",
            "  p               Preview text file",
            "",
            "Create:",
            "  n               Create new file",
            "  m               Create new directory",
            "",
            "View:",
            "  .               Show/hide hidden files",
            "  F5              Refresh",
            "",
            "Panel Mode:",
            "  F2              Toggle dual panel mode",
            "  TAB             Switch between panels (dual mode only)",
            "",
            "Other:",
            "  ?               Show this help",
            "  q / Esc         Quit",
            "",
            "CD-on-exit:",
            "  Use 'fmc' command to change terminal directory on exit",
            "  (requires sourcing fm_wrapper.sh in your shell)",
            "",
            "Press any key to continue..."
        ]
        
        # Temporarily disable nodelay and set infinite timeout for help screen
        self.stdscr.nodelay(False)
        self.stdscr.timeout(-1)
        
        # Clear screen and draw help
        self.stdscr.clear()
        height, width = self.stdscr.getmaxyx()
        
        # Draw help text
        for i, line in enumerate(help_text):
            if i >= height - 1:
                break
            try:
                if i == 0:  # Title
                    self.stdscr.addstr(i, 0, line[:width-1], curses.A_BOLD | curses.color_pair(5))
                elif line.startswith("  ") and line.strip():  # Command lines
                    # Split command and description
                    parts = line.split(None, 1)
                    if len(parts) >= 2:
                        cmd = parts[0]
                        desc = " ".join(parts[1:]) if len(parts) > 1 else ""
                        self.stdscr.addstr(i, 2, cmd[:15], curses.A_BOLD | curses.color_pair(2))
                        if len(cmd) < 15:
                            self.stdscr.addstr(i, 2 + len(cmd), " " * (15 - len(cmd)) + desc[:width-17])
                    else:
                        self.stdscr.addstr(i, 0, line[:width-1])
                elif line.endswith(":"):  # Section headers
                    self.stdscr.addstr(i, 0, line[:width-1], curses.A_BOLD | curses.color_pair(1))
                else:  # Regular lines
                    self.stdscr.addstr(i, 0, line[:width-1])
            except curses.error:
                pass
        
        # Refresh and wait for key
        self.stdscr.refresh()
        key = self.stdscr.getch()
        
        # Restore original settings
        self.stdscr.nodelay(True)
        self.stdscr.timeout(100)
        
        # Clear the entire screen buffer to prevent flicker
        self.stdscr.erase()
        self.stdscr.refresh()

    def toggle_selection(self):
        """Toggle selection of current file"""
        if not self.files or self.selected_index >= len(self.files):
            return
        
        # All files can now be selected (no parent directory entry)
        
        if self.selected_index in self.selected_files:
            self.selected_files.remove(self.selected_index)
            filename = self.files[self.selected_index][0]
            self.show_message(f"Deselected: {filename}")
        else:
            self.selected_files.add(self.selected_index)
            filename = self.files[self.selected_index][0]
            self.show_message(f"Selected: {filename}")
    
    def clear_selection(self):
        """Clear all selections"""
        count = len(self.selected_files)
        self.selected_files.clear()
        if count > 0:
            self.show_message(f"Cleared {count} selections")
        else:
            self.show_message("No files selected")
    
    def select_all(self):
        """Select all files (except parent directory)"""
        count = 0
        for i, file_info in enumerate(self.files):
            if i not in self.selected_files:
                self.selected_files.add(i)
                count += 1
        
        if count > 0:
            self.show_message(f"Selected {count} additional files")
        else:
            self.show_message("All files already selected")

    def toggle_hidden(self):
        """Toggle showing hidden files"""
        self.show_hidden = not self.show_hidden
        self.refresh_files()
        status = "ON" if self.show_hidden else "OFF"
        self.show_message(f"Hidden files: {status}")

    def start_search(self):
        """Start search mode"""
        # Save current settings
        self.stdscr.nodelay(False)
        self.stdscr.timeout(-1)
        curses.curs_set(1)
        curses.echo()
        
        try:
            self.stdscr.clear()
            height, width = self.stdscr.getmaxyx()
            prompt = "Search files (name): "
            
            self.stdscr.addstr(height//2, 0, prompt, curses.A_BOLD)
            self.stdscr.addstr(height//2 + 2, 0, "Press Enter to search, ESC to cancel")
            self.stdscr.refresh()
            
            # Position cursor after prompt
            self.stdscr.move(height//2, len(prompt))
            
            # Custom input handling to support ESC
            search_query = self.get_dialog_input(height//2, len(prompt), 50)
            
            if search_query is None:
                # User pressed ESC
                self.show_message("Search cancelled")
            elif search_query.strip():
                self.search_query = search_query.lower()
                self.search_mode = True
                self.filter_mode = False  # Disable filter when searching
                self.apply_search_filter()
                self.show_message(f"Searching for: {search_query}")
            else:
                # Empty string - cancel search/filter
                self.clear_search_filter()
                
        except KeyboardInterrupt:
            self.show_message("Search cancelled")
        except Exception as e:
            self.show_message(f"Search error: {e}", error=True)
        finally:
            curses.curs_set(0)
            curses.noecho()
            self.stdscr.nodelay(True)
            self.stdscr.timeout(100)
    
    def start_filter(self):
        """Start filter by extension mode"""
        # Save current settings
        self.stdscr.nodelay(False)
        self.stdscr.timeout(-1)
        curses.curs_set(1)
        curses.echo()
        
        try:
            self.stdscr.clear()
            height, width = self.stdscr.getmaxyx()
            prompt = "Filter by extension (e.g., .txt, .mp3): "
            
            self.stdscr.addstr(height//2, 0, prompt, curses.A_BOLD)
            self.stdscr.addstr(height//2 + 2, 0, "Press Enter to filter, ESC to cancel")
            self.stdscr.refresh()
            
            # Position cursor after prompt
            self.stdscr.move(height//2, len(prompt))
            
            # Custom input handling to support ESC
            filter_ext = self.get_dialog_input(height//2, len(prompt), 20)
            
            if filter_ext is None:
                # User pressed ESC
                self.show_message("Filter cancelled")
            elif filter_ext.strip():
                filter_ext = filter_ext.lower().strip()
                # Ensure extension starts with .
                if not filter_ext.startswith('.'):
                    filter_ext = '.' + filter_ext
                
                self.filter_extension = filter_ext
                self.filter_mode = True
                self.search_mode = False  # Disable search when filtering
                self.apply_search_filter()
                self.show_message(f"Filtering by: {filter_ext}")
            else:
                # Empty string - cancel search/filter
                self.clear_search_filter()
                
        except KeyboardInterrupt:
            self.show_message("Filter cancelled")
        except Exception as e:
            self.show_message(f"Filter error: {e}", error=True)
        finally:
            curses.curs_set(0)
            curses.noecho()
            self.stdscr.nodelay(True)
            self.stdscr.timeout(100)
    
    def apply_search_filter(self):
        """Apply current search or filter to file list"""
        if not self.original_files:
            self.original_files = self.files.copy()
        
        filtered_files = []
        
        # Apply search or filter to all files
        for file_info in self.original_files:
            filename = file_info[0]
            
            # Apply search filter
            if self.search_mode and self.search_query:
                if self.search_query in filename.lower():
                    filtered_files.append(file_info)
            
            # Apply extension filter
            elif self.filter_mode and self.filter_extension:
                if filename.lower().endswith(self.filter_extension):
                    filtered_files.append(file_info)
        
        self.files = filtered_files
        self.selected_index = 0
        self.scroll_offset = 0
        self.selected_files.clear()
        
        # Update panel data if in dual panel mode
        if self.dual_panel_mode:
            self.panel_files[self.active_panel] = self.files
            self.panel_selected_index[self.active_panel] = 0
            self.panel_scroll_offset[self.active_panel] = 0
            self.panel_selected_files[self.active_panel].clear()
    
    def clear_search_filter(self):
        """Clear search/filter and restore original file list"""
        if self.original_files:
            self.files = self.original_files.copy()
            self.original_files = []
        
        self.search_mode = False
        self.filter_mode = False
        self.search_query = ""
        self.filter_extension = ""
        self.selected_index = 0
        self.scroll_offset = 0
        self.selected_files.clear()
        
        # Update panel data if in dual panel mode
        if self.dual_panel_mode:
            self.panel_files[self.active_panel] = self.files
            self.panel_selected_index[self.active_panel] = 0
            self.panel_scroll_offset[self.active_panel] = 0
            self.panel_selected_files[self.active_panel].clear()
        
        self.show_message("Search/filter cleared")
    
    def get_dialog_input(self, y, x, max_length):
        """Get input from user with ESC support"""
        input_str = ""
        cursor_pos = 0
        
        while True:
            # Display current input
            try:
                # Clear the input area
                self.stdscr.addstr(y, x, "" * max_length)
                # Show current input with cursor
                display_str = input_str[:max_length-1]
                self.stdscr.addstr(y, x, display_str)
                # Position cursor
                self.stdscr.move(y, x + min(cursor_pos, len(display_str)))
                self.stdscr.refresh()
            except curses.error:
                pass
            
            # Get key
            key = self.stdscr.getch()
            
            if key == 27:  # ESC
                return None
            elif key == ord('\n') or key == ord('\r') or key == curses.KEY_ENTER:
                # Enter - return current input
                return input_str
            elif key == curses.KEY_BACKSPACE or key == 127 or key == 8:
                # Backspace
                if cursor_pos > 0:
                    input_str = input_str[:cursor_pos-1] + input_str[cursor_pos:]
                    cursor_pos -= 1
            elif key == curses.KEY_LEFT:
                # Left arrow
                if cursor_pos > 0:
                    cursor_pos -= 1
            elif key == curses.KEY_RIGHT:
                # Right arrow
                if cursor_pos < len(input_str):
                    cursor_pos += 1
            elif key == curses.KEY_HOME or key == 1:  # Ctrl+A
                # Home - go to beginning
                cursor_pos = 0
            elif key == curses.KEY_END or key == 5:  # Ctrl+E
                # End - go to end
                cursor_pos = len(input_str)
            elif 32 <= key <= 126:  # Printable ASCII
                # Regular character
                if len(input_str) < max_length - 1:
                    char = chr(key)
                    input_str = input_str[:cursor_pos] + char + input_str[cursor_pos:]
                    cursor_pos += 1
    
    def quick_preview(self):
        """Quick preview of text files"""
        if not self.files or self.selected_index >= len(self.files):
            return
        
        selected_file = self.files[self.selected_index]
        filename = selected_file[0]
        
        if len(selected_file) > 1 and selected_file[1]:  # Directory
            self.show_message("Cannot preview directories", error=True)
            return
        
        filepath = self.current_path / filename
        
        # Check if file is likely to be text
        try:
            # Check file size (limit to reasonable size)
            if filepath.stat().st_size > 1024 * 1024:  # 1MB limit
                self.show_message("File too large for preview (>1MB)", error=True)
                return
            
            # Try to read as text
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(4096)  # Read first 4KB
            
            self.show_preview_window(filename, content)
            
        except PermissionError:
            self.show_message("Permission denied", error=True)
        except UnicodeDecodeError:
            self.show_message("File is not a text file", error=True)
        except Exception as e:
            self.show_message(f"Preview error: {e}", error=True)
    
    def show_preview_window(self, filename, content):
        """Show preview window with file content"""
        # Save current settings
        self.stdscr.nodelay(False)
        self.stdscr.timeout(-1)
        
        self.stdscr.clear()
        height, width = self.stdscr.getmaxyx()
        
        # Draw title
        title = f"Preview: {filename}"
        try:
            self.stdscr.addstr(0, 0, title[:width-1], curses.color_pair(5) | curses.A_BOLD)
        except curses.error:
            pass
        
        # Draw content
        lines = content.split('\n')
        visible_height = height - 3
        
        for i, line in enumerate(lines[:visible_height]):
            y_pos = i + 1
            if y_pos >= height - 2:
                break
            
            try:
                # Replace tabs with spaces and limit line length
                display_line = line.expandtabs(4)[:width-1]
                self.stdscr.addstr(y_pos, 0, display_line)
            except curses.error:
                pass
        
        # Draw footer
        footer = "Press any key to close preview"
        try:
            self.stdscr.addstr(height-1, 0, footer[:width-1], curses.color_pair(5))
        except curses.error:
            pass
        
        self.stdscr.refresh()
        
        # Wait for any key
        self.stdscr.getch()
        
        # Restore settings
        self.stdscr.nodelay(True)
        self.stdscr.timeout(100)

    def save_current_directory(self):
        """Save current directory to temp file for shell cd functionality"""
        if self.cd_on_exit and self.temp_file:
            try:
                with open(self.temp_file, 'w') as f:
                    f.write(str(self.current_path))
            except Exception:
                pass  # Silently fail if we can't write the temp file

    def run(self):
        """Main program loop"""
        # Set non-blocking input with timeout
        self.stdscr.nodelay(True)
        self.stdscr.timeout(100)
        
        while True:
            self.draw_screen()
            
            key = self.stdscr.getch()
            
            # Skip timeout events
            if key == -1:
                continue
            
            # Arrow key navigation
            if key == curses.KEY_UP:
                self.navigate_up()
            elif key == curses.KEY_DOWN:
                self.navigate_down()
            elif key == curses.KEY_LEFT:
                self.navigate_left()
            elif key == curses.KEY_RIGHT:
                self.navigate_right()
            
            # Vim-style navigation
            elif key == ord('k'):
                self.navigate_up()
            elif key == ord('j'):
                self.navigate_down()
            elif key == ord('h'):
                self.navigate_left()
            elif key == ord('l'):
                self.navigate_right()
            
            # Enter directory or open file
            elif key == curses.KEY_ENTER or key == 10 or key == 13:
                self.enter_directory()
            elif key == curses.KEY_BACKSPACE or key == 127:
                self.navigate_left()
            
            # File operations
            elif key == ord('c'):
                self.copy_file()
            elif key == ord('x'):
                self.cut_file()
            elif key == ord('v'):
                self.paste_file()
            elif key == ord('d'):
                self.delete_file()
            elif key == ord('r'):
                self.rename_file()
            elif key == ord('o'):
                self.open_file()
            
            # Create new
            elif key == ord('n'):
                self.create_file()
            elif key == ord('m'):
                self.create_directory()
            
            # Multi-selection
            elif key == ord(' '):  # Space to toggle selection
                self.toggle_selection()
            elif key == ord('a'):  # Select all
                self.select_all()
            elif key == ord('A'):  # Clear all selections
                self.clear_selection()
            
            # Panel management
            elif key == curses.KEY_F2:
                self.toggle_dual_panel()
            elif key == ord('\t'):  # Tab key
                if self.dual_panel_mode:
                    self.switch_panel()
                else:
                    self.show_message("Tab only works in dual panel mode")
            
            # Search and filter
            elif key == ord('s'):  # Search
                self.start_search()
            elif key == ord('f'):  # Filter
                self.start_filter()
            elif key == ord('\\') or key == 27:  # Backslash or ESC to clear
                if self.search_mode or self.filter_mode:
                    self.clear_search_filter()
                else:
                    # ESC for quit if no search/filter active
                    self.save_current_directory()
                    break
            elif key == ord('p'):  # Preview
                self.quick_preview()
            
            # View options
            elif key == ord('.'):
                self.toggle_hidden()
            elif key == curses.KEY_F5:
                self.refresh_files()
                self.show_message("Refreshed")
            
            # Help and quit
            elif key == ord('?'):
                self.show_help()
            elif key == ord('q'):
                self.save_current_directory()
                break


def main(stdscr, cd_on_exit=False, temp_file=None):
    """Main function to run the file manager"""
    try:
        # Initialize screen properly
        curses.noecho()
        curses.cbreak()
        stdscr.keypad(True)
        
        # Initialize file manager
        fm = FileManager(stdscr, cd_on_exit, temp_file)
        fm.run()
        
    except Exception as e:
        # Make sure we clean up properly on error
        curses.endwin()
        print(f"Error in file manager: {e}")
        raise
    finally:
        # Restore terminal state
        try:
            curses.nocbreak()
            stdscr.keypad(False)
            curses.echo()
        except:
            pass


if __name__ == "__main__":
    import sys
    import tempfile
    
    # Parse command line arguments
    cd_on_exit = False
    temp_file = None
    
    if len(sys.argv) > 1 and sys.argv[1] == "--cd":
        cd_on_exit = True
        # Create a temporary file to store the directory
        temp_fd, temp_file = tempfile.mkstemp(suffix='.filemanager')
        os.close(temp_fd)  # Close the file descriptor, we'll use the filename
        print(temp_file)  # Print the temp file path for the shell wrapper to read
    
    try:
        curses.wrapper(main, cd_on_exit, temp_file)
    except KeyboardInterrupt:
        if not cd_on_exit:
            print("\nFile manager interrupted by user")
    except Exception as e:
        if not cd_on_exit:
            print(f"Error running file manager: {e}")
    finally:
        # Clean up temp file if it exists and we're not using it for cd
        if temp_file and not cd_on_exit:
            try:
                os.unlink(temp_file)
            except:
                pass
