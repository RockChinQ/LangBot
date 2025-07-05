
import PyPDF2
from docx import Document
import pandas as pd
import csv
import chardet
from typing import Union, List, Callable, Any
import logging
import markdown
from bs4 import BeautifulSoup
import ebooklib
from ebooklib import epub
import re
import asyncio # Import asyncio for async operations
import os

# Configure logging
logger = logging.getLogger(__name__)

class FileParser:
    """
    A robust file parser class to extract text content from various document formats.
    It supports TXT, PDF, DOCX, XLSX, CSV, Markdown, HTML, and EPUB files.
    All core file reading operations are designed to be run synchronously in a thread pool
    to avoid blocking the asyncio event loop.
    """
    def __init__(self):
        
        self.logger = logging.getLogger(self.__class__.__name__)

    async def _run_sync(self, sync_func: Callable, *args: Any, **kwargs: Any) -> Any:
        """
        Runs a synchronous function in a separate thread to prevent blocking the event loop.
        This is a general utility method for wrapping blocking I/O operations.
        """
        try:
            return await asyncio.to_thread(sync_func, *args, **kwargs)
        except Exception as e:
            self.logger.error(f"Error running synchronous function {sync_func.__name__}: {e}")
            raise

    async def parse(self, file_path: str) -> Union[str, None]:
        """
        Parses the file based on its extension and returns the extracted text content.
        This is the main asynchronous entry point for parsing.
        
        Args:
            file_path (str): The path to the file to be parsed.

        Returns:
            Union[str, None]: The extracted text content as a single string, or None if parsing fails.
        """
        if not file_path or not os.path.exists(file_path):
            self.logger.error(f"Invalid file path provided: {file_path}")
            return None

        file_extension = file_path.split('.')[-1].lower()
        parser_method = getattr(self, f'_parse_{file_extension}', None)
        
        if parser_method is None:
            self.logger.error(f"Unsupported file format: {file_extension} for file {file_path}")
            return None
        
        try:
            # Pass file_path to the specific parser methods
            return await parser_method(file_path)
        except Exception as e:
            self.logger.error(f"Failed to parse {file_extension} file {file_path}: {e}")
            return None

    # --- Helper for reading files with encoding detection ---
    async def _read_file_content(self, file_path: str, mode: str = 'r') -> Union[str, bytes]:
        """
        Reads a file with automatic encoding detection, ensuring the synchronous
        file read operation runs in a separate thread.
        """
        def _read_sync():
            with open(file_path, 'rb') as file:
                raw_data = file.read()
                detected = chardet.detect(raw_data)
                encoding = detected['encoding'] or 'utf-8'
            
            if mode == 'r':
                return raw_data.decode(encoding, errors='ignore')
            return raw_data # For binary mode

        return await self._run_sync(_read_sync)

    # --- Specific Parser Methods ---

    async def _parse_txt(self, file_path: str) -> str:
        """Parses a TXT file and returns its content."""
        self.logger.info(f"Parsing TXT file: {file_path}")
        return await self._read_file_content(file_path, mode='r')

    async def _parse_pdf(self, file_path: str) -> str:
        """Parses a PDF file and returns its text content."""
        self.logger.info(f"Parsing PDF file: {file_path}")
        def _parse_pdf_sync():
            text_content = []
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text = page.extract_text()
                    if text:
                        text_content.append(text)
            return '\n'.join(text_content)
        return await self._run_sync(_parse_pdf_sync)

    async def _parse_docx(self, file_path: str) -> str:
        """Parses a DOCX file and returns its text content."""
        self.logger.info(f"Parsing DOCX file: {file_path}")
        def _parse_docx_sync():
            doc = Document(file_path)
            text_content = [paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip()]
            return '\n'.join(text_content)
        return await self._run_sync(_parse_docx_sync)
    
    async def _parse_doc(self, file_path: str) -> str:
        """Handles .doc files, explicitly stating lack of direct support."""
        self.logger.warning(f"Direct .doc parsing is not supported for {file_path}. Please convert to .docx first.")
        raise NotImplementedError("Direct .doc parsing not supported. Please convert to .docx first.")
        
    async def _parse_xlsx(self, file_path: str) -> str:
        """Parses an XLSX file, returning text from all sheets."""
        self.logger.info(f"Parsing XLSX file: {file_path}")
        def _parse_xlsx_sync():
            excel_file = pd.ExcelFile(file_path)
            all_sheet_content = []
            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                sheet_text = f"--- Sheet: {sheet_name} ---\n{df.to_string(index=False)}\n"
                all_sheet_content.append(sheet_text)
            return '\n'.join(all_sheet_content)
        return await self._run_sync(_parse_xlsx_sync)
        
    async def _parse_csv(self, file_path: str) -> str:
        """Parses a CSV file and returns its content as a string."""
        self.logger.info(f"Parsing CSV file: {file_path}")
        def _parse_csv_sync():
            # pd.read_csv can often detect encoding, but explicit detection is safer
            raw_data = self._read_file_content(file_path, mode='rb') # Note: this will need to be await outside this sync function
            # For simplicity, we'll let pandas handle encoding internally after a raw read.
            # A more robust solution might pass encoding directly to pd.read_csv after detection.
            detected = chardet.detect(open(file_path, 'rb').read())
            encoding = detected['encoding'] or 'utf-8'
            df = pd.read_csv(file_path, encoding=encoding)
            return df.to_string(index=False)
        return await self._run_sync(_parse_csv_sync)
    
    async def _parse_markdown(self, file_path: str) -> str:
        """Parses a Markdown file, converting it to structured plain text."""
        self.logger.info(f"Parsing Markdown file: {file_path}")
        def _parse_markdown_sync():
            md_content = self._read_file_content(file_path, mode='r') # This is a synchronous call within a sync function
            html_content = markdown.markdown(
                md_content,
                extensions=['extra', 'codehilite', 'tables', 'toc', 'fenced_code']
            )
            soup = BeautifulSoup(html_content, 'html.parser')
            text_parts = []
            for element in soup.children:
                if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    level = int(element.name[1])
                    text_parts.append('#' * level + ' ' + element.get_text().strip())
                elif element.name == 'p':
                    text = element.get_text().strip()
                    if text:
                        text_parts.append(text)
                elif element.name in ['ul', 'ol']:
                    for li in element.find_all('li'):
                        text_parts.append(f"* {li.get_text().strip()}")
                elif element.name == 'pre':
                    code_block = element.get_text().strip()
                    if code_block:
                        text_parts.append(f"```\n{code_block}\n```")
                elif element.name == 'table':
                    table_str = self._extract_table_to_markdown_sync(element) # Call sync helper
                    if table_str:
                        text_parts.append(table_str)
                elif element.name:
                    text = element.get_text(separator=' ', strip=True)
                    if text:
                        text_parts.append(text)
            cleaned_text = re.sub(r'\n\s*\n', '\n\n', '\n'.join(text_parts))
            return cleaned_text.strip()
        return await self._run_sync(_parse_markdown_sync)

    async def _parse_html(self, file_path: str) -> str:
        """Parses an HTML file, extracting structured plain text."""
        self.logger.info(f"Parsing HTML file: {file_path}")
        def _parse_html_sync():
            html_content = self._read_file_content(file_path, mode='r') # Sync call within sync function
            soup = BeautifulSoup(html_content, 'html.parser')
            for script_or_style in soup(["script", "style"]):
                script_or_style.decompose()
            text_parts = []
            for element in soup.body.children if soup.body else soup.children:
                if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    level = int(element.name[1])
                    text_parts.append('#' * level + ' ' + element.get_text().strip())
                elif element.name == 'p':
                    text = element.get_text().strip()
                    if text:
                        text_parts.append(text)
                elif element.name in ['ul', 'ol']:
                    for li in element.find_all('li'):
                        text = li.get_text().strip()
                        if text:
                            text_parts.append(f"* {text}")
                elif element.name == 'table':
                    table_str = self._extract_table_to_markdown_sync(element) # Call sync helper
                    if table_str:
                        text_parts.append(table_str)
                elif element.name:
                    text = element.get_text(separator=' ', strip=True)
                    if text:
                        text_parts.append(text)
            cleaned_text = re.sub(r'\n\s*\n', '\n\n', '\n'.join(text_parts))
            return cleaned_text.strip()
        return await self._run_sync(_parse_html_sync)
    
    async def _parse_epub(self, file_path: str) -> str:
        """Parses an EPUB file, extracting metadata and content."""
        self.logger.info(f"Parsing EPUB file: {file_path}")
        def _parse_epub_sync():
            book = epub.read_epub(file_path)
            text_content = []
            title_meta = book.get_metadata('DC', 'title')
            if title_meta:
                text_content.append(f"Title: {title_meta[0][0]}")
            creator_meta = book.get_metadata('DC', 'creator')
            if creator_meta:
                text_content.append(f"Author: {creator_meta[0][0]}")
            date_meta = book.get_metadata('DC', 'date')
            if date_meta:
                text_content.append(f"Publish Date: {date_meta[0][0]}")
            toc = book.get_toc()
            if toc:
                text_content.append("\n--- Table of Contents ---")
                self._add_toc_items_sync(toc, text_content, level=0) # Call sync helper
                text_content.append("--- End of Table of Contents ---\n")
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    html_content = item.get_content().decode('utf-8', errors='ignore')
                    soup = BeautifulSoup(html_content, 'html.parser')
                    for junk in soup(["script", "style", "nav", "header", "footer"]):
                        junk.decompose()
                    text = soup.get_text(separator='\n', strip=True)
                    text = re.sub(r'\n\s*\n', '\n\n', text)
                    if text:
                        text_content.append(text)
            return re.sub(r'\n\s*\n', '\n\n', '\n'.join(text_content)).strip()
        return await self._run_sync(_parse_epub_sync)

    def _add_toc_items_sync(self, toc_list: list, text_content: list, level: int):
        """Recursively adds TOC items to text_content (synchronous helper)."""
        indent = '  ' * level
        for item in toc_list:
            if isinstance(item, tuple):
                chapter, subchapters = item
                text_content.append(f"{indent}- {chapter.title}")
                self._add_toc_items_sync(subchapters, text_content, level + 1)
            else:
                text_content.append(f"{indent}- {item.title}")

    def _extract_table_to_markdown_sync(self, table_element: BeautifulSoup) -> str:
        """Helper to convert a BeautifulSoup table element into a Markdown table string (synchronous)."""
        headers = [th.get_text().strip() for th in table_element.find_all('th')]
        rows = []
        for tr in table_element.find_all('tr'):
            cells = [td.get_text().strip() for td in tr.find_all('td')]
            if cells:
                rows.append(cells)
        
        if not headers and not rows:
            return ""

        table_lines = []
        if headers:
            table_lines.append(' | '.join(headers))
            table_lines.append(' | '.join(['---'] * len(headers)))
        
        for row_cells in rows:
            padded_cells = row_cells + [''] * (len(headers) - len(row_cells)) if headers else row_cells
            table_lines.append(' | '.join(padded_cells))
        
        return '\n'.join(table_lines)