import sys
import requests
import re
from pathlib import Path
from typing import List
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QTextEdit, QListWidget, QLabel,
    QFileDialog, QMessageBox, QProgressBar, QSplitter, QRadioButton,
    QButtonGroup
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
import html2text


class FetchThread(QThread):
    """后台线程用于抓取网页内容"""
    progress = Signal(int, int)
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, urls: List[str]):
        super().__init__()
        self.urls = urls
        self.h = html2text.HTML2Text()
        self.h.ignore_links = False
        self.h.ignore_images = False
        self.h.body_width = 0

    def run(self):
        results = []
        for i, url in enumerate(self.urls):
            try:
                response = requests.get(url, timeout=10, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                response.raise_for_status()
                response.encoding = response.apparent_encoding
                markdown_content = self.h.handle(response.text)

                results.append({
                    'url': url,
                    'content': markdown_content,
                    'success': True
                })
            except Exception as e:
                results.append({
                    'url': url,
                    'content': f'错误: {str(e)}',
                    'success': False
                })

            self.progress.emit(i + 1, len(self.urls))

        self.finished.emit(results)


class MarkdownMerger(QMainWindow):
    def __init__(self):
        super().__init__()
        self.url_list = []
        self.markdown_results = []
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('网页转Markdown工具')
        self.setGeometry(100, 100, 1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 标题
        title_label = QLabel('网页转Markdown工具')
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        # URL输入
        url_layout = QHBoxLayout()
        url_label = QLabel('URL:')
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText('输入网页URL，按回车添加')
        self.url_input.returnPressed.connect(self.add_url)
        self.add_btn = QPushButton('添加')
        self.add_btn.clicked.connect(self.add_url)

        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input)
        url_layout.addWidget(self.add_btn)
        main_layout.addLayout(url_layout)

        # 分割器
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：URL列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        list_label = QLabel('URL列表:')
        left_layout.addWidget(list_label)

        self.url_list_widget = QListWidget()
        left_layout.addWidget(self.url_list_widget)

        list_btn_layout = QHBoxLayout()
        self.remove_btn = QPushButton('移除')
        self.remove_btn.clicked.connect(self.remove_url)
        self.clear_btn = QPushButton('清空')
        self.clear_btn.clicked.connect(self.clear_urls)
        list_btn_layout.addWidget(self.remove_btn)
        list_btn_layout.addWidget(self.clear_btn)
        left_layout.addLayout(list_btn_layout)

        splitter.addWidget(left_widget)

        # 右侧：预览
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        preview_label = QLabel('预览:')
        right_layout.addWidget(preview_label)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText('抓取完成后显示内容')
        right_layout.addWidget(self.preview_text)

        splitter.addWidget(right_widget)
        splitter.setSizes([400, 800])
        main_layout.addWidget(splitter)

        # 保存选项
        save_option_layout = QHBoxLayout()
        save_option_label = QLabel('保存方式:')
        self.merge_radio = QRadioButton('合并为一个文件')
        self.merge_radio.setChecked(True)
        self.split_radio = QRadioButton('分别保存为多个文件')

        self.save_mode_group = QButtonGroup()
        self.save_mode_group.addButton(self.merge_radio)
        self.save_mode_group.addButton(self.split_radio)

        save_option_layout.addWidget(save_option_label)
        save_option_layout.addWidget(self.merge_radio)
        save_option_layout.addWidget(self.split_radio)
        save_option_layout.addStretch()
        main_layout.addLayout(save_option_layout)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # 底部按钮
        bottom_layout = QHBoxLayout()
        self.fetch_btn = QPushButton('开始抓取')
        self.fetch_btn.clicked.connect(self.start_fetch)
        self.fetch_btn.setStyleSheet('QPushButton { background-color: #4CAF50; color: white; padding: 10px; }')

        self.save_btn = QPushButton('保存文件')
        self.save_btn.clicked.connect(self.save_markdown)
        self.save_btn.setEnabled(False)
        self.save_btn.setStyleSheet('QPushButton { background-color: #2196F3; color: white; padding: 10px; }')

        bottom_layout.addWidget(self.fetch_btn)
        bottom_layout.addWidget(self.save_btn)
        main_layout.addLayout(bottom_layout)

        self.statusBar().showMessage('就绪')

    def add_url(self):
        url = self.url_input.text().strip()
        if url:
            if url.startswith('http://') or url.startswith('https://'):
                self.url_list.append(url)
                self.url_list_widget.addItem(url)
                self.url_input.clear()
                self.statusBar().showMessage(f'已添加: {url}')
            else:
                QMessageBox.warning(self, '无效URL', 'URL必须以http://或https://开头')

    def remove_url(self):
        current_row = self.url_list_widget.currentRow()
        if current_row >= 0:
            self.url_list.pop(current_row)
            self.url_list_widget.takeItem(current_row)

    def clear_urls(self):
        self.url_list.clear()
        self.url_list_widget.clear()

    def start_fetch(self):
        if not self.url_list:
            QMessageBox.warning(self, '提示', '请先添加URL')
            return

        self.fetch_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(len(self.url_list))

        self.fetch_thread = FetchThread(self.url_list.copy())
        self.fetch_thread.progress.connect(self.update_progress)
        self.fetch_thread.finished.connect(self.fetch_completed)
        self.fetch_thread.start()

        self.statusBar().showMessage('正在抓取...')

    def update_progress(self, current, total):
        self.progress_bar.setValue(current)
        self.statusBar().showMessage(f'抓取: {current}/{total}')

    def fetch_completed(self, results):
        self.markdown_results = results

        # 显示预览（合并内容）
        merged_content = []
        success_count = sum(1 for r in results if r['success'])

        for result in results:
            merged_content.append(f"# {result['url']}\n\n")
            merged_content.append(result['content'])
            merged_content.append("\n\n---\n\n")

        self.preview_text.setPlainText(''.join(merged_content))

        self.fetch_btn.setEnabled(True)
        self.save_btn.setEnabled(True)
        self.progress_bar.setVisible(False)

        self.statusBar().showMessage(f'完成: {success_count}/{len(results)} 成功')

    def get_filename_from_url(self, url):
        """从URL提取文件名（使用最后两级路径）"""
        # 移除协议和参数
        path = url.split('://')[-1].split('?')[0].split('#')[0]
        # 分离域名和路径
        parts = path.split('/')
        domain = parts[0] if parts else 'page'
        path_parts = [p for p in parts[1:] if p]  # 过滤空字符串

        # 根据路径部分数量决定文件名
        if len(path_parts) >= 2:
            # 取最后两级
            filename = f"{path_parts[-2]}_{path_parts[-1]}"
        elif len(path_parts) == 1:
            # 只有一级，使用域名和路径
            filename = f"{domain.split('.')[0]}_{path_parts[0]}"
        else:
            # 没有路径，使用域名
            filename = domain.split('.')[0]

        # 清理非法字符
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # 移除扩展名（如.html）
        filename = filename.rsplit('.', 1)[0] if '.' in filename else filename
        return filename or 'page'

    def save_markdown(self):
        if not self.markdown_results:
            return

        if self.merge_radio.isChecked():
            # 合并保存
            file_path, _ = QFileDialog.getSaveFileName(
                self, '保存Markdown文件', 'merged.md', 'Markdown (*.md)'
            )
            if file_path:
                try:
                    content = self.preview_text.toPlainText()
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    QMessageBox.information(self, '成功', f'已保存到:\n{file_path}')
                except Exception as e:
                    QMessageBox.critical(self, '错误', f'保存失败:\n{str(e)}')
        else:
            # 分别保存
            folder = QFileDialog.getExistingDirectory(self, '选择保存文件夹')
            if folder:
                success_count = 0
                for result in self.markdown_results:
                    if result['success']:
                        filename = self.get_filename_from_url(result['url'])
                        file_path = Path(folder) / f"{filename}.md"

                        # 处理文件名冲突
                        counter = 1
                        while file_path.exists():
                            file_path = Path(folder) / f"{filename}_{counter}.md"
                            counter += 1

                        try:
                            with open(file_path, 'w', encoding='utf-8') as f:
                                f.write(f"# {result['url']}\n\n")
                                f.write(result['content'])
                            success_count += 1
                        except Exception as e:
                            print(f"保存失败 {filename}: {e}")

                QMessageBox.information(
                    self, '完成',
                    f'成功保存 {success_count}/{len(self.markdown_results)} 个文件到:\n{folder}'
                )


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = MarkdownMerger()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()