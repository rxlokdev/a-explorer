#!/usr/bin/env python3
"""
A-Explorer: A retro-style file manager with Windows XP styling
Compatible with Windows 7, 8, 10, 11
"""

import os
import sys
import shutil
import time
import threading
import subprocess
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import fnmatch

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    print("Warning: pygame not available - music player disabled")

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("Warning: opencv-python not available - video player disabled")

class AExplorer:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("A-Explorer")
        self.root.geometry("800x600")
        self.root.minsize(640, 480)
        
        self.colors = {
            'bg': '#ECE9D8',
            'fg': '#000000',
            'select': '#316AC5',
            'border': '#0058B8',
            'button': '#F1F1F1',
            'button_hover': '#B8D6F0',
            'button_active': '#94C1F7',
            'text_bg': '#FFFFFF',
            'titlebar': '#0058B8',
            'titlebar_text': '#FFFFFF',
            'statusbar': '#ECE9D8',
            'retro_blue': '#000080'
        }
        
        self.current_path = Path.cwd()
        self.selected_file = None
        self.clipboard_action = None
        self.clipboard_item = None
        
        self.music_playing = False
        self.music_paused = False
        self.current_music_file = None
        self.video_window = None
        self.video_playing = False
        
        if PYGAME_AVAILABLE:
            pygame.mixer.init()
        
        self.search_results = []
        self.search_index = 0
        
        self.root.configure(bg=self.colors['bg'])
        
        self.setup_ui()
        self.refresh_file_list()
        
        self.root.bind('<F5>', lambda e: self.refresh_file_list())
        self.root.bind('<Delete>', self.delete_selected)
        self.root.bind('<Return>', self.open_selected)
        self.root.bind('<F2>', self.rename_selected)
        self.root.bind('<Control-c>', self.copy_selected)
        self.root.bind('<Control-x>', self.cut_selected)
        self.root.bind('<Control-v>', self.paste_selected)
        self.root.bind('<Control-f>', self.open_search_dialog)
        self.root.bind('<F3>', lambda e: self.play_selected_media())
        self.root.bind('<F4>', lambda e: self.stop_media())
        
    def setup_ui(self):
        main_frame = tk.Frame(self.root, bg=self.colors['bg'])
        main_frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        title_frame = tk.Frame(main_frame, height=30, bg=self.colors['titlebar'], relief='raised', borderwidth=2)
        title_frame.pack(fill="x", padx=2, pady=2)
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(title_frame, text="A-Explorer", 
                              fg=self.colors['titlebar_text'], bg=self.colors['titlebar'],
                              font=('Tahoma', 16, 'bold'))
        title_label.pack(side="left", padx=5, pady=5)
        
        self.path_label = tk.Label(title_frame, text=str(self.current_path),
                                   fg=self.colors['titlebar_text'], bg=self.colors['titlebar'],
                                   font=('Tahoma', 12))
        self.path_label.pack(side="left", padx=20, pady=5)
        
        toolbar_frame = tk.Frame(main_frame, height=35, bg=self.colors['bg'], relief='sunken', borderwidth=2)
        toolbar_frame.pack(fill="x", padx=2, pady=2)
        toolbar_frame.pack_propagate(False)
        
        buttons = [
            ("↑ Parent", self.go_parent),
            ("← Back", self.go_back),
            ("→ Forward", self.go_forward),
            ("↻ Refresh", self.refresh_file_list),
            ("+ New", self.create_new),
            ("× Delete", self.delete_selected),
            ("🔍 Search", self.open_search_dialog),
            ("▶ Play", self.play_selected_media),
            ("■ Stop", self.stop_media)
        ]
        
        for text, command in buttons:
            btn = tk.Button(toolbar_frame, text=text, command=command,
                           bg=self.colors['button'], fg='black',
                           width=8, height=1,
                           relief='raised', borderwidth=2,
                           font=('Tahoma', 8, 'bold'),
                           activebackground=self.colors['button_active'])
            btn.pack(side="left", padx=2, pady=5)
            
            btn.bind('<Enter>', lambda e, b=btn: b.configure(bg=self.colors['button_hover']))
            btn.bind('<Leave>', lambda e, b=btn: b.configure(bg=self.colors['button']))
        
        content_frame = tk.Frame(main_frame, bg=self.colors['bg'])
        content_frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        list_frame = tk.Frame(content_frame, bg=self.colors['bg'], relief='sunken', borderwidth=2)
        list_frame.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")
        
        self.file_listbox = tk.Listbox(list_frame, 
                                      bg=self.colors['text_bg'],
                                      fg=self.colors['fg'],
                                      selectbackground=self.colors['select'],
                                      selectforeground=self.colors['titlebar_text'],
                                      font=('Tahoma', 10),
                                      borderwidth=0,
                                      relief='flat',
                                      yscrollcommand=scrollbar.set)
        self.file_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.file_listbox.yview)
        self.file_listbox.bind('<Double-Button-1>', self.on_double_click)
        self.file_listbox.bind('<<ListboxSelect>>', self.on_select)
        
        info_frame = tk.Frame(content_frame, width=200, bg=self.colors['bg'], relief='sunken', borderwidth=2)
        info_frame.pack(side="right", fill="y", padx=2, pady=2)
        info_frame.pack_propagate(False)
        
        info_label = tk.Label(info_frame, text="File Info",
                             fg=self.colors['fg'], bg=self.colors['bg'],
                             font=('Tahoma', 14, 'bold'))
        info_label.pack(pady=10)
        
        self.info_text = tk.Text(info_frame, height=8, width=22,
                                bg=self.colors['text_bg'], fg=self.colors['fg'],
                                font=('Tahoma', 9),
                                borderwidth=1, relief='solid',
                                insertbackground=self.colors['fg'])
        self.info_text.pack(padx=5, pady=5)
        
        media_frame = tk.Frame(info_frame, bg=self.colors['bg'], relief='groove', borderwidth=2)
        media_frame.pack(pady=10, padx=5, fill="x")
        
        media_label = tk.Label(media_frame, text="Media Controls",
                              fg=self.colors['fg'], bg=self.colors['bg'],
                              font=('Tahoma', 12, 'bold'))
        media_label.pack(pady=5)
        
        music_frame = tk.Frame(media_frame, bg=self.colors['bg'])
        music_frame.pack(pady=5)
        
        self.music_status = tk.Label(music_frame, text="Music: Stopped",
                                   fg=self.colors['fg'], bg=self.colors['bg'],
                                   font=('Tahoma', 9))
        self.music_status.pack()
        
        music_btn_frame = tk.Frame(music_frame, bg=self.colors['bg'])
        music_btn_frame.pack(pady=2)
        
        play_btn = tk.Button(music_btn_frame, text="▶", command=self.toggle_music,
                           bg=self.colors['button'], fg='black', width=4, height=1,
                           relief='raised', borderwidth=2, font=('Tahoma', 8, 'bold'),
                           activebackground=self.colors['button_active'])
        play_btn.pack(side="left", padx=1)
        play_btn.bind('<Enter>', lambda e, b=play_btn: b.configure(bg=self.colors['button_hover']))
        play_btn.bind('<Leave>', lambda e, b=play_btn: b.configure(bg=self.colors['button']))
        
        pause_btn = tk.Button(music_btn_frame, text="⏸", command=self.pause_music,
                            bg=self.colors['button'], fg='black', width=4, height=1,
                            relief='raised', borderwidth=2, font=('Tahoma', 8, 'bold'),
                            activebackground=self.colors['button_active'])
        pause_btn.pack(side="left", padx=1)
        pause_btn.bind('<Enter>', lambda e, b=pause_btn: b.configure(bg=self.colors['button_hover']))
        pause_btn.bind('<Leave>', lambda e, b=pause_btn: b.configure(bg=self.colors['button']))
        
        stop_btn = tk.Button(music_btn_frame, text="■", command=self.stop_music,
                           bg=self.colors['button'], fg='black', width=4, height=1,
                           relief='raised', borderwidth=2, font=('Tahoma', 8, 'bold'),
                           activebackground=self.colors['button_active'])
        stop_btn.pack(side="left", padx=1)
        stop_btn.bind('<Enter>', lambda e, b=stop_btn: b.configure(bg=self.colors['button_hover']))
        stop_btn.bind('<Leave>', lambda e, b=stop_btn: b.configure(bg=self.colors['button']))
        
        status_frame = tk.Frame(main_frame, height=20, bg=self.colors['statusbar'], relief='sunken', borderwidth=2)
        status_frame.pack(fill="x", padx=2, pady=2)
        status_frame.pack_propagate(False)
        
        self.status_bar = tk.Label(status_frame, text="Ready",
                                  fg=self.colors['fg'], bg=self.colors['statusbar'],
                                  font=('Tahoma', 9), anchor='w')
        self.status_bar.pack(fill="x", padx=5, pady=2)
        
        self.history = [self.current_path]
        self.history_index = 0
        
    def refresh_file_list(self):
        self.file_listbox.delete(0, tk.END)
        
        try:
            items = []
            for item in sorted(self.current_path.iterdir()):
                if item.is_dir():
                    items.append((item, True))
            
            for item in sorted(self.current_path.iterdir()):
                if item.is_file():
                    items.append((item, False))
            
            for item, is_dir in items:
                display_name = item.name
                if is_dir:
                    display_name = f"[{display_name}]"
                self.file_listbox.insert(tk.END, display_name)
                
            self.update_status(f"Showing {len(items)} items")
            
        except PermissionError:
            messagebox.showerror("Error", "Access denied")
            self.update_status("Access denied")
    
    def on_double_click(self, event):
        self.open_selected()
    
    def on_select(self, event):
        selection = self.file_listbox.curselection()
        if selection:
            index = selection[0]
            item_text = self.file_listbox.get(index)
            
            if item_text.startswith('[') and item_text.endswith(']'):
                item_text = item_text[1:-1]
            
            self.selected_file = self.current_path / item_text
            self.update_info_panel()
        else:
            self.selected_file = None
            self.clear_info_panel()
    
    def update_info_panel(self):
        if not self.selected_file:
            return
            
        self.info_text.delete("1.0", "end")
        
        try:
            stat = self.selected_file.stat()
            info = f"Name: {self.selected_file.name}\n"
            info += f"Type: {'Directory' if self.selected_file.is_dir() else 'File'}\n"
            
            if self.selected_file.is_file():
                size = stat.st_size
                if size < 1024:
                    info += f"Size: {size} bytes\n"
                elif size < 1024 * 1024:
                    info += f"Size: {size/1024:.1f} KB\n"
                else:
                    info += f"Size: {size/(1024*1024):.1f} MB\n"
            
            info += f"Modified: {datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')}\n"
            
            self.info_text.insert("1.0", info)
            
        except Exception as e:
            self.info_text.insert("1.0", f"Error: {str(e)}")
    
    def clear_info_panel(self):
        self.info_text.delete("1.0", "end")
    
    def open_selected(self):
        if not self.selected_file:
            return
            
        if self.selected_file.is_dir():
            self.navigate_to(self.selected_file)
        else:
            try:
                os.startfile(self.selected_file)
            except Exception as e:
                messagebox.showerror("Error", f"Cannot open file: {str(e)}")
    
    def navigate_to(self, path):
        if path != self.current_path and path.exists() and path.is_dir():
            self.current_path = path.resolve()
            
            if self.history_index < len(self.history) - 1:
                self.history = self.history[:self.history_index + 1]
            self.history.append(self.current_path)
            self.history_index = len(self.history) - 1
            
            self.path_label.configure(text=str(self.current_path))
            self.refresh_file_list()
    
    def go_parent(self):
        parent = self.current_path.parent
        if parent != self.current_path:
            self.navigate_to(parent)
    
    def go_back(self):
        if self.history_index > 0:
            self.history_index -= 1
            self.current_path = self.history[self.history_index]
            self.path_label.configure(text=str(self.current_path))
            self.refresh_file_list()
    
    def go_forward(self):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.current_path = self.history[self.history_index]
            self.path_label.configure(text=str(self.current_path))
            self.refresh_file_list()
    
    def delete_selected(self):
        if not self.selected_file:
            return
            
        if messagebox.askyesno("Confirm Delete", 
                              f"Delete {self.selected_file.name}?"):
            try:
                if self.selected_file.is_dir():
                    shutil.rmtree(self.selected_file)
                else:
                    self.selected_file.unlink()
                self.refresh_file_list()
                self.update_status(f"Deleted {self.selected_file.name}")
            except Exception as e:
                messagebox.showerror("Error", f"Cannot delete: {str(e)}")
    
    def rename_selected(self):
        if not self.selected_file:
            return
            
        dialog = tk.Toplevel(self.root)
        dialog.title("Rename")
        dialog.geometry("300x120")
        dialog.configure(bg=self.colors['bg'])
        dialog.resizable(False, False)
        
        dialog_frame = tk.Frame(dialog, bg=self.colors['bg'], relief='raised', borderwidth=2)
        dialog_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        tk.Label(dialog_frame, text="Enter new name:", fg=self.colors['fg'], 
                bg=self.colors['bg'], font=('Tahoma', 10)).pack(pady=10)
        
        entry = tk.Entry(dialog_frame, font=('Tahoma', 10), bg=self.colors['text_bg'], 
                       fg=self.colors['fg'], relief='solid', borderwidth=1)
        entry.pack(pady=5, padx=10, fill="x")
        entry.insert(0, self.selected_file.name)
        entry.select_range(0, tk.END)
        
        button_frame = tk.Frame(dialog_frame, bg=self.colors['bg'])
        button_frame.pack(pady=10)
        
        def do_rename():
            new_name = entry.get()
            if new_name and new_name != self.selected_file.name:
                try:
                    new_path = self.selected_file.parent / new_name
                    self.selected_file.rename(new_path)
                    self.refresh_file_list()
                    self.update_status(f"Renamed to {new_name}")
                except Exception as e:
                    messagebox.showerror("Error", f"Cannot rename: {str(e)}")
            dialog.destroy()
        
        ok_btn = tk.Button(button_frame, text="OK", command=do_rename,
                         bg=self.colors['button'], fg='black', width=10,
                         relief='raised', borderwidth=2, font=('Tahoma', 9),
                         activebackground=self.colors['button_active'])
        ok_btn.pack(side="left", padx=5)
        ok_btn.bind('<Enter>', lambda e, b=ok_btn: b.configure(bg=self.colors['button_hover']))
        ok_btn.bind('<Leave>', lambda e, b=ok_btn: b.configure(bg=self.colors['button']))
        
        cancel_btn = tk.Button(button_frame, text="Cancel", command=dialog.destroy,
                             bg=self.colors['button'], fg='black', width=10,
                             relief='raised', borderwidth=2, font=('Tahoma', 9),
                             activebackground=self.colors['button_active'])
        cancel_btn.pack(side="left", padx=5)
        cancel_btn.bind('<Enter>', lambda e, b=cancel_btn: b.configure(bg=self.colors['button_hover']))
        cancel_btn.bind('<Leave>', lambda e, b=cancel_btn: b.configure(bg=self.colors['button']))
        
        entry.bind('<Return>', lambda e: do_rename())
        entry.focus()
    
    def create_new(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("New Folder")
        dialog.geometry("300x120")
        dialog.configure(bg=self.colors['bg'])
        dialog.resizable(False, False)
        
        dialog_frame = tk.Frame(dialog, bg=self.colors['bg'], relief='raised', borderwidth=2)
        dialog_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        tk.Label(dialog_frame, text="Enter name for new folder:", fg=self.colors['fg'], 
                bg=self.colors['bg'], font=('Tahoma', 10)).pack(pady=10)
        
        entry = tk.Entry(dialog_frame, font=('Tahoma', 10), bg=self.colors['text_bg'],
                       fg=self.colors['fg'], relief='solid', borderwidth=1)
        entry.pack(pady=5, padx=10, fill="x")
        
        button_frame = tk.Frame(dialog_frame, bg=self.colors['bg'])
        button_frame.pack(pady=10)
        
        def do_create():
            name = entry.get()
            if name:
                try:
                    new_path = self.current_path / name
                    new_path.mkdir()
                    self.refresh_file_list()
                    self.update_status(f"Created folder {name}")
                except Exception as e:
                    messagebox.showerror("Error", f"Cannot create folder: {str(e)}")
            dialog.destroy()
        
        create_btn = tk.Button(button_frame, text="Create", command=do_create,
                             bg=self.colors['button'], fg='black', width=10,
                             relief='raised', borderwidth=2, font=('Tahoma', 9),
                             activebackground=self.colors['button_active'])
        create_btn.pack(side="left", padx=5)
        create_btn.bind('<Enter>', lambda e, b=create_btn: b.configure(bg=self.colors['button_hover']))
        create_btn.bind('<Leave>', lambda e, b=create_btn: b.configure(bg=self.colors['button']))
        
        cancel_btn = tk.Button(button_frame, text="Cancel", command=dialog.destroy,
                             bg=self.colors['button'], fg='black', width=10,
                             relief='raised', borderwidth=2, font=('Tahoma', 9),
                             activebackground=self.colors['button_active'])
        cancel_btn.pack(side="left", padx=5)
        cancel_btn.bind('<Enter>', lambda e, b=cancel_btn: b.configure(bg=self.colors['button_hover']))
        cancel_btn.bind('<Leave>', lambda e, b=cancel_btn: b.configure(bg=self.colors['button']))
        
        entry.bind('<Return>', lambda e: do_create())
        entry.focus()
    
    def copy_selected(self):
        if self.selected_file:
            self.clipboard_action = 'copy'
            self.clipboard_item = self.selected_file
            self.update_status(f"Copied {self.selected_file.name}")
    
    def cut_selected(self):
        if self.selected_file:
            self.clipboard_action = 'cut'
            self.clipboard_item = self.selected_file
            self.update_status(f"Cut {self.selected_file.name}")
    
    def paste_selected(self):
        if hasattr(self, 'clipboard_item'):
            try:
                if self.clipboard_action == 'copy':
                    if self.clipboard_item.is_file():
                        shutil.copy2(self.clipboard_item, self.current_path)
                    else:
                        shutil.copytree(self.clipboard_item, self.current_path / self.clipboard_item.name)
                elif self.clipboard_action == 'cut':
                    shutil.move(str(self.clipboard_item), str(self.current_path / self.clipboard_item.name))
                
                self.refresh_file_list()
                self.update_status(f"Pasted {self.clipboard_item.name}")
            except Exception as e:
                messagebox.showerror("Error", f"Cannot paste: {str(e)}")
    
    def update_status(self, message):
        self.status_bar.configure(text=message)
        self.root.update_idletasks()
    
    def play_selected_media(self):
        if not self.selected_file or not self.selected_file.is_file():
            messagebox.showwarning("Warning", "Please select a media file")
            return
        
        file_ext = self.selected_file.suffix.lower()
        
        music_extensions = {'.mp3', '.wav', '.ogg', '.flac', '.m4a', '.wma'}
        video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv'}
        
        if file_ext in music_extensions:
            self.play_music(self.selected_file)
        elif file_ext in video_extensions:
            self.play_video(self.selected_file)
        else:
            messagebox.showinfo("Info", f"Unsupported media format: {file_ext}")
    
    def play_music(self, music_file):
        if not PYGAME_AVAILABLE:
            messagebox.showerror("Error", "pygame not available for music playback")
            return
        
        try:
            self.stop_music()
            pygame.mixer.music.load(str(music_file))
            pygame.mixer.music.play()
            self.music_playing = True
            self.music_paused = False
            self.current_music_file = music_file
            self.music_status.configure(text=f"Playing: {music_file.name}")
            self.update_status(f"Playing music: {music_file.name}")
            
            threading.Thread(target=self.monitor_music, daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Cannot play music: {str(e)}")
    
    def toggle_music(self):
        if not PYGAME_AVAILABLE:
            return
        
        if self.music_playing and not self.music_paused:
            self.pause_music()
        elif self.current_music_file:
            pygame.mixer.music.unpause()
            self.music_paused = False
            self.music_status.configure(text=f"Playing: {self.current_music_file.name}")
    
    def pause_music(self):
        if not PYGAME_AVAILABLE:
            return
        
        if self.music_playing and not self.music_paused:
            pygame.mixer.music.pause()
            self.music_paused = True
            self.music_status.configure(text=f"Paused: {self.current_music_file.name}")
    
    def stop_music(self):
        if not PYGAME_AVAILABLE:
            return
        
        if self.music_playing:
            pygame.mixer.music.stop()
            self.music_playing = False
            self.music_paused = False
            self.current_music_file = None
            self.music_status.configure(text="Music: Stopped")
            self.update_status("Music stopped")
    
    def monitor_music(self):
        while self.music_playing:
            time.sleep(0.5)
            if not pygame.mixer.music.get_busy() and self.music_playing:
                self.music_playing = False
                self.music_paused = False
                self.current_music_file = None
                self.root.after(0, lambda: self.music_status.configure(text="Music: Stopped"))
                break
    
    def play_video(self, video_file):
        if not CV2_AVAILABLE:
            try:
                os.startfile(video_file)
                self.update_status(f"Opening video with default player: {video_file.name}")
            except Exception as e:
                messagebox.showerror("Error", f"Cannot play video: {str(e)}")
            return
        
        if self.video_window:
            self.video_window.destroy()
        
        self.video_window = tk.Toplevel(self.root)
        self.video_window.title(f"Video Player - {video_file.name}")
        self.video_window.geometry("640x480")
        self.video_window.configure(bg=self.colors['bg'])
        
        control_frame = tk.Frame(self.video_window, bg=self.colors['bg'])
        control_frame.pack(fill="x", pady=5)
        
        tk.Button(control_frame, text="Play/Pause", command=self.toggle_video,
                 bg=self.colors['button'], fg='black').pack(side="left", padx=5)
        tk.Button(control_frame, text="Stop", command=self.stop_video,
                 bg=self.colors['button'], fg='black').pack(side="left", padx=5)
        tk.Button(control_frame, text="Close", command=self.close_video_window,
                 bg=self.colors['button'], fg='black').pack(side="left", padx=5)
        
        self.video_label = tk.Label(self.video_window, bg='black')
        self.video_label.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.video_playing = True
        self.current_video_file = video_file
        threading.Thread(target=self.play_video_thread, args=(video_file,), daemon=True).start()
    
    def play_video_thread(self, video_file):
        try:
            cap = cv2.VideoCapture(str(video_file))
            
            while self.video_playing and cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame_resized = cv2.resize(frame_rgb, (640, 480))
                
                try:
                    from PIL import Image, ImageTk
                    image = Image.fromarray(frame_resized)
                    photo = ImageTk.PhotoImage(image=image)
                    
                    self.root.after(0, lambda p=photo: self.update_video_frame(p))
                    
                except ImportError:
                    break
                
                time.sleep(0.033)
            
            cap.release()
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Video playback error: {str(e)}"))
        
        finally:
            self.video_playing = False
    
    def update_video_frame(self, photo):
        if self.video_label and self.video_playing:
            self.video_label.configure(image=photo)
            self.video_label.image = photo
    
    def toggle_video(self):
        self.video_playing = not self.video_playing
        if self.video_playing and self.current_video_file:
            threading.Thread(target=self.play_video_thread, args=(self.current_video_file,), daemon=True).start()
    
    def stop_video(self):
        self.video_playing = False
    
    def close_video_window(self):
        self.video_playing = False
        if self.video_window:
            self.video_window.destroy()
            self.video_window = None
    
    def stop_media(self):
        self.stop_music()
        self.stop_video()
        self.close_video_window()
    
    def open_search_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Search Files")
        dialog.geometry("450x250")
        dialog.configure(bg=self.colors['bg'])
        dialog.resizable(False, False)
        
        dialog_frame = tk.Frame(dialog, bg=self.colors['bg'], relief='raised', borderwidth=2)
        dialog_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        tk.Label(dialog_frame, text="Search for files:", fg=self.colors['fg'], 
                bg=self.colors['bg'], font=('Tahoma', 12, 'bold')).pack(pady=10)
        
        search_frame = tk.Frame(dialog_frame, bg=self.colors['bg'])
        search_frame.pack(pady=5, padx=10, fill="x")
        
        tk.Label(search_frame, text="Pattern:", fg=self.colors['fg'], 
                bg=self.colors['bg'], font=('Tahoma', 10)).pack(side="left", padx=5)
        
        search_entry = tk.Entry(search_frame, font=('Tahoma', 10), width=25,
                               bg=self.colors['text_bg'], fg=self.colors['fg'],
                               relief='solid', borderwidth=1)
        search_entry.pack(side="left", padx=5)
        search_entry.focus()
        
        options_frame = tk.Frame(dialog_frame, bg=self.colors['bg'])
        options_frame.pack(pady=10, padx=10)
        
        include_subdirs = tk.BooleanVar(value=True)
        cb = tk.Checkbutton(options_frame, text="Include subdirectories", variable=include_subdirs,
                          fg=self.colors['fg'], bg=self.colors['bg'], selectcolor=self.colors['text_bg'],
                          font=('Tahoma', 9), relief='flat')
        cb.pack()
        
        def do_search():
            pattern = search_entry.get()
            if pattern:
                self.search_files(pattern, include_subdirs.get())
                self.show_search_results()
            dialog.destroy()
        
        button_frame = tk.Frame(dialog_frame, bg=self.colors['bg'])
        button_frame.pack(pady=15)
        
        search_btn = tk.Button(button_frame, text="Search", command=do_search,
                              bg=self.colors['button'], fg='black', width=12,
                              relief='raised', borderwidth=2, font=('Tahoma', 9),
                              activebackground=self.colors['button_active'])
        search_btn.pack(side="left", padx=5)
        search_btn.bind('<Enter>', lambda e, b=search_btn: b.configure(bg=self.colors['button_hover']))
        search_btn.bind('<Leave>', lambda e, b=search_btn: b.configure(bg=self.colors['button']))
        
        cancel_btn = tk.Button(button_frame, text="Cancel", command=dialog.destroy,
                             bg=self.colors['button'], fg='black', width=12,
                             relief='raised', borderwidth=2, font=('Tahoma', 9),
                             activebackground=self.colors['button_active'])
        cancel_btn.pack(side="left", padx=5)
        cancel_btn.bind('<Enter>', lambda e, b=cancel_btn: b.configure(bg=self.colors['button_hover']))
        cancel_btn.bind('<Leave>', lambda e, b=cancel_btn: b.configure(bg=self.colors['button']))
        
        search_entry.bind('<Return>', lambda e: do_search())
    
    def search_files(self, pattern, include_subdirs=True):
        self.search_results = []
        self.search_index = 0
        
        try:
            if include_subdirs:
                for root, dirs, files in os.walk(self.current_path):
                    for file in files:
                        if fnmatch.fnmatch(file.lower(), pattern.lower()):
                            self.search_results.append(Path(root) / file)
            else:
                for file in self.current_path.iterdir():
                    if file.is_file() and fnmatch.fnmatch(file.name.lower(), pattern.lower()):
                        self.search_results.append(file)
            
            self.update_status(f"Found {len(self.search_results)} files matching '{pattern}'")
            
        except Exception as e:
            messagebox.showerror("Error", f"Search error: {str(e)}")
    
    def show_search_results(self):
        if not self.search_results:
            messagebox.showinfo("Search Results", "No files found")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Search Results")
        dialog.geometry("550x450")
        dialog.configure(bg=self.colors['bg'])
        
        dialog_frame = tk.Frame(dialog, bg=self.colors['bg'], relief='raised', borderwidth=2)
        dialog_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        tk.Label(dialog_frame, text=f"Found {len(self.search_results)} files:",
                fg=self.colors['fg'], bg=self.colors['bg'],
                font=('Tahoma', 12, 'bold')).pack(pady=10)
        
        results_frame = tk.Frame(dialog_frame, bg=self.colors['bg'], relief='sunken', borderwidth=2)
        results_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        scrollbar = tk.Scrollbar(results_frame)
        scrollbar.pack(side="right", fill="y")
        
        results_listbox = tk.Listbox(results_frame, 
                                    bg=self.colors['text_bg'], fg=self.colors['fg'],
                                    selectbackground=self.colors['select'],
                                    selectforeground=self.colors['titlebar_text'],
                                    font=('Tahoma', 9),
                                    yscrollcommand=scrollbar.set,
                                    relief='flat', borderwidth=0)
        results_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=results_listbox.yview)
        
        for file_path in self.search_results:
            results_listbox.insert(tk.END, str(file_path))
        
        def open_selected_result():
            selection = results_listbox.curselection()
            if selection:
                selected_path = Path(results_listbox.get(selection[0]))
                if selected_path.is_file():
                    os.startfile(selected_path)
                elif selected_path.parent != self.current_path:
                    self.navigate_to(selected_path.parent)
                    dialog.destroy()
        
        def navigate_to_result():
            selection = results_listbox.curselection()
            if selection:
                selected_path = Path(results_listbox.get(selection[0]))
                if selected_path.parent != self.current_path:
                    self.navigate_to(selected_path.parent)
                    dialog.destroy()
        
        button_frame = tk.Frame(dialog_frame, bg=self.colors['bg'])
        button_frame.pack(fill="x", padx=10, pady=10)
        
        open_btn = tk.Button(button_frame, text="Open", command=open_selected_result,
                           bg=self.colors['button'], fg='black', width=12,
                           relief='raised', borderwidth=2, font=('Tahoma', 9),
                           activebackground=self.colors['button_active'])
        open_btn.pack(side="left", padx=5)
        open_btn.bind('<Enter>', lambda e, b=open_btn: b.configure(bg=self.colors['button_hover']))
        open_btn.bind('<Leave>', lambda e, b=open_btn: b.configure(bg=self.colors['button']))
        
        goto_btn = tk.Button(button_frame, text="Go to Folder", command=navigate_to_result,
                           bg=self.colors['button'], fg='black', width=12,
                           relief='raised', borderwidth=2, font=('Tahoma', 9),
                           activebackground=self.colors['button_active'])
        goto_btn.pack(side="left", padx=5)
        goto_btn.bind('<Enter>', lambda e, b=goto_btn: b.configure(bg=self.colors['button_hover']))
        goto_btn.bind('<Leave>', lambda e, b=goto_btn: b.configure(bg=self.colors['button']))
        
        close_btn = tk.Button(button_frame, text="Close", command=dialog.destroy,
                            bg=self.colors['button'], fg='black', width=12,
                            relief='raised', borderwidth=2, font=('Tahoma', 9),
                            activebackground=self.colors['button_active'])
        close_btn.pack(side="right", padx=5)
        close_btn.bind('<Enter>', lambda e, b=close_btn: b.configure(bg=self.colors['button_hover']))
        close_btn.bind('<Leave>', lambda e, b=close_btn: b.configure(bg=self.colors['button']))
        
        results_listbox.bind('<Double-Button-1>', lambda e: open_selected_result())
    
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = AExplorer()
    app.run()
