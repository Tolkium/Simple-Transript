"""
Video Transcriber

Description:
    A tool that generates SRT subtitle files from video content using both:
    - Word-level transcription (precise timing for each word)
    - Sentence-level transcription (complete sentences with timestamps)

Features:
    - Multi-language support
    - Multiple transcription model options
    - Customizable character limits
    - Configurable character filtering

Author: [Marek Šípoš]
Version: 1.0
"""

import tkinter as tk
from tkinter import ttk, filedialog
import os
import json
import whisper
import whisper_timestamped
from pathlib import Path
import pyperclip
from tkinter import IntVar, StringVar, BooleanVar

# Constants
MODELS = ["tiny", "base", "small", "medium"]
LANGUAGES = ["English", "Dutch", "German", "Slovak"]
SETTINGS_FILE = "transcriber_settings.json"

class Settings:
    def __init__(self):
        self.settings_path = Path(__file__).parent / SETTINGS_FILE
        self.default_settings = {
            "input_directory": "",
            "output_directory": "",
            "language": "English",
            "model": "tiny",
            "word_level": True,
            "sentence_level": False,
            "char_limit": 20,
            "chars_to_remove": "",
        }
        self.current = self.load()
    
    def load(self):
        try:
            with open(self.settings_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return self.default_settings.copy()
    
    def save(self):
        with open(self.settings_path, 'w') as f:
            json.dump(self.current, f, indent=4)

class TranscriberGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Video Transcriber")
        self.settings = Settings()
        
        # Variables
        self.files = []
        self.output_dir = self.settings.current["output_directory"]  # Add this line
        self.char_limit = IntVar(value=self.settings.current["char_limit"])
        self.model_var = StringVar(value=self.settings.current["model"])
        self.language_var = StringVar(value=self.settings.current["language"])
        self.word_level_var = BooleanVar(value=self.settings.current["word_level"])
        self.sentence_level_var = BooleanVar(value=self.settings.current["sentence_level"])
        self.chars_to_remove = StringVar(value=self.settings.current["chars_to_remove"])
        
        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        # Create grouped sections with borders
        model_frame = ttk.LabelFrame(main_frame, text="Model Settings", padding="10")
        model_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        
        text_frame = ttk.LabelFrame(main_frame, text="Text Settings", padding="10")
        text_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        
        file_frame = ttk.LabelFrame(main_frame, text="File Management", padding="10")
        file_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=5)

        # Model Settings Group
        ttk.Label(model_frame, text="Model:").grid(row=0, column=0, sticky="e", padx=5)
        ttk.Combobox(model_frame, textvariable=self.model_var, values=MODELS, width=25).grid(row=0, column=1, sticky="w", padx=5)
        
        ttk.Label(model_frame, text="Language:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        ttk.Combobox(model_frame, textvariable=self.language_var, values=LANGUAGES, width=25).grid(row=1, column=1, sticky="w", padx=5)
        
        # Text Settings Group
        mode_frame = ttk.Frame(text_frame)
        mode_frame.grid(row=0, column=0, columnspan=2, pady=5)
        
        ttk.Checkbutton(mode_frame, text="Word-level", variable=self.word_level_var, command=self.toggle_char_limit).pack(side=tk.LEFT, padx=10)
        ttk.Checkbutton(mode_frame, text="Sentence-level", variable=self.sentence_level_var).pack(side=tk.LEFT, padx=10)
        
        ttk.Label(text_frame, text="Characters to remove:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        ttk.Entry(text_frame, textvariable=self.chars_to_remove, width=25).grid(row=1, column=1, sticky="w", padx=5)
        
        self.char_frame = ttk.Frame(text_frame)
        self.char_frame.grid(row=2, column=0, columnspan=2, pady=5)
        ttk.Label(self.char_frame, text="Characters per line:").pack(side=tk.LEFT, padx=5)
        self.char_spinbox = ttk.Spinbox(self.char_frame, from_=1, to=100, textvariable=self.char_limit, width=10)
        self.char_spinbox.pack(side=tk.LEFT, padx=5)

        # File Management Group
        button_frame = ttk.Frame(file_frame)
        button_frame.grid(row=0, column=0, columnspan=2, pady=5)
        
        ttk.Button(button_frame, text="Select Files", command=self.select_files, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Output Folder", command=self.select_output, width=15).pack(side=tk.LEFT, padx=5)
        
        self.files_label = ttk.Label(file_frame, text="No files selected")
        self.files_label.grid(row=1, column=0, columnspan=2, pady=5)
        
        self.output_label = ttk.Label(file_frame, text=self.settings.current["output_directory"] or "No folder selected")
        self.output_label.grid(row=2, column=0, columnspan=2, pady=5)

        # Bottom Section
        ttk.Button(main_frame, text="Transcribe", command=self.transcribe, style="Accent.TButton").grid(row=3, column=0, columnspan=2, pady=15)
        
        self.progress = ttk.Progressbar(main_frame, length=300, mode='determinate')
        self.progress.grid(row=4, column=0, columnspan=2, pady=5)
        
        self.error_var = tk.StringVar()
        error_label = ttk.Label(main_frame, textvariable=self.error_var, wraplength=300)
        error_label.grid(row=5, column=0, columnspan=2, pady=5)
        error_label.bind('<Button-1>', self.copy_error)

        # Make layout expandable
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Initial states
        self.toggle_char_limit()

    def toggle_char_limit(self):
        if self.word_level_var.get():
            self.char_spinbox.configure(state='normal')
            self.char_frame.grid()
        else:
            self.char_spinbox.configure(state='disabled')
            self.char_frame.grid_remove()

    def save_settings(self):
        self.settings.current.update({
            "input_directory": os.path.dirname(self.files[0]) if self.files else "",
            "output_directory": self.output_dir,
            "language": self.language_var.get(),
            "model": self.model_var.get(),
            "word_level": self.word_level_var.get(),
            "sentence_level": self.sentence_level_var.get(),
            "char_limit": self.char_limit.get(),
            "chars_to_remove": self.chars_to_remove.get()
        })
        self.settings.save()

    def select_files(self):
        initial_dir = self.settings.current["input_directory"]
        self.files = filedialog.askopenfilenames(
            filetypes=[("Video files", "*.mp4")],
            initialdir=initial_dir if initial_dir else None
        )
        if self.files:
            self.files_label.config(text=f"{len(self.files)} files selected")
            self.save_settings()

    def select_output(self):
        initial_dir = self.settings.current["output_directory"]
        self.output_dir = filedialog.askdirectory(initialdir=initial_dir if initial_dir else None)
        if self.output_dir:
            self.output_label.config(text=self.output_dir)
            self.save_settings()

    def copy_error(self, event):
        error_text = self.error_var.get()
        if error_text:
            pyperclip.copy(error_text)

    def transcribe(self):
        if not self.files:
            self.error_var.set("Please select input files")
            return
        if not self.output_dir:
            self.error_var.set("Please select output folder")
            return
        if not (self.word_level_var.get() or self.sentence_level_var.get()):
            self.error_var.set("Please select at least one transcription mode")
            return

        try:
            # Load models
            if self.word_level_var.get():
                word_model = whisper_timestamped.load_model(self.model_var.get(), device="cpu")
            if self.sentence_level_var.get():
                sentence_model = whisper.load_model(self.model_var.get())

            total_files = len(self.files)
            
            for i, file in enumerate(self.files):
                base_filename = os.path.basename(file).rsplit(".", 1)[0]
                
                # Word-level transcription
                if self.word_level_var.get():
                    result = whisper_timestamped.transcribe(
                        word_model, 
                        file,
                        language=self.language_var.get().lower()
                    )
                    word_srt_path = self.get_unique_filename(
                        os.path.join(self.output_dir, f"{base_filename}_full.srt")
                    )
                    self.create_word_srt(result, word_srt_path)

                # Sentence-level transcription
                if self.sentence_level_var.get():
                    result = sentence_model.transcribe(
                        file,
                        language=self.language_var.get().lower()
                    )
                    sent_srt_path = self.get_unique_filename(
                        os.path.join(self.output_dir, f"{base_filename}_cropped.srt")
                    )
                    self.create_sentence_srt(result, sent_srt_path)

                self.progress['value'] = ((i + 1) / total_files) * 100
                self.root.update()

            self.error_var.set("Transcription completed!")

        except Exception as e:
            self.error_var.set(str(e))

    def create_word_srt(self, result, output_file):
        current_text = ""
        current_start = None
        subtitle_count = 1

        with open(output_file, "w", encoding="utf-8") as f:
            for segment in result['segments']:
                for word in segment['words']:
                    cleaned_word = self.clean_text(word['text'])
                    if not cleaned_word.strip():
                        continue
                        
                    if current_start is None:
                        current_start = word['start']

                    if len(current_text + cleaned_word) > self.char_limit.get():
                        end_time = word['start']
                        f.write(f"{subtitle_count}\n")
                        f.write(f"{self.format_timestamp(current_start)} --> {self.format_timestamp(end_time)}\n")
                        f.write(f"{current_text.strip()}\n\n")

                        subtitle_count += 1
                        current_text = cleaned_word + " "
                        current_start = word['start']
                    else:
                        current_text += cleaned_word + " "

            if current_text:
                f.write(f"{subtitle_count}\n")
                f.write(f"{self.format_timestamp(current_start)} --> {self.format_timestamp(segment['end'])}\n")
                f.write(f"{current_text.strip()}\n")

    def create_sentence_srt(self, result, output_file):
        subtitle_count = 1
        
        with open(output_file, "w", encoding="utf-8") as f:
            for segment in result['segments']:
                start_time = segment['start']
                end_time = segment['end']
                cleaned_text = self.clean_text(segment['text']).strip()
                
                if not cleaned_text:
                    continue
                    
                f.write(f"{subtitle_count}\n")
                f.write(f"{self.format_timestamp(start_time)} --> {self.format_timestamp(end_time)}\n")
                f.write(f"{cleaned_text}\n\n")
                
                subtitle_count += 1

    def format_timestamp(self, seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def get_unique_filename(self, filepath):
        path = Path(filepath)
        stem = path.stem
        
        import re
        match = re.match(r"(.*?)\((\d+)\)$", stem)
        
        if match:
            base_name = match.group(1)
            counter = int(match.group(2))
            stem = f"{base_name}({counter + 1})"
        else:
            stem = f"{stem}(1)"
        
        new_path = path.parent / f"{stem}{path.suffix}"
        
        while new_path.exists():
            match = re.match(r"(.*?)\((\d+)\)$", stem)
            base_name = match.group(1)
            counter = int(match.group(2))
            stem = f"{base_name}({counter + 1})"
            new_path = path.parent / f"{stem}{path.suffix}"
        
        return str(new_path)

    def run(self):
        # Set initial size and position
        window_width = 500
        window_height = 600
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        self.root.mainloop()

    def clean_text(self, text):
        chars = self.chars_to_remove.get().split()
        for char in chars:
            text = text.replace(char, '')
        return text

if __name__ == "__main__":
    app = TranscriberGUI()
    app.run()