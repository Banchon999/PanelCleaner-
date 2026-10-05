from functools import partial, wraps
from pathlib import Path

import PySide6.QtCore as Qc
import PySide6.QtGui as Qg
import PySide6.QtWidgets as Qw
from PySide6.QtCore import Slot
from attrs import define
from loguru import logger
from natsort import natsorted

import pcleaner.config as cfg
import pcleaner.gui.gui_utils as gu
import pcleaner.gui.image_file as imf
import pcleaner.gui.state_saver as ss
import pcleaner.gui.worker_thread as wt
import pcleaner.structures as st
import pcleaner.translation.glossary as gl
import pcleaner.translation.translator as trl
from pcleaner.gui.ocr_review_driver import WrapTextDelegate
from pcleaner.gui.ui_generated_files.ui_TranslationReview import Ui_TranslationReview
from pcleaner.helpers import f_plural

LABEL_COLUMN = 0
ORIGINAL_COLUMN = 1
TRANSLATION_COLUMN = 2

COLOR_NORMAL = Qg.QColor(0, 128, 0, 255)
COLOR_EDITED = Qg.QColor(0, 0, 128, 255)
COLOR_MISSING = Qg.QColor(128, 0, 0, 255)


def suppress_cell_update_handling(method):
    """
    The cellChanged signal also fires when the table is filled programmatically,
    only treat changes as user input outside of these methods.
    """

    @wraps(method)
    def wrapper(self, *args, **kwargs):
        self.awaiting_user_input = False
        result = method(self, *args, **kwargs)
        self.awaiting_user_input = True
        return result

    return wrapper


@define
class TranslationRow:
    """
    One bubble in the review.

    label: The bubble number shown on the image.
    box: The bubble's box on the original image. Plain text files have no boxes (all -1).
    text: The original text.
    translation: The current translation, possibly edited by the user.
    machine_translation: The latest translation from the model, to tell edits apart and undo them.
    """

    label: str
    box: st.Box
    text: str
    translation: str
    machine_translation: str

    @property
    def edited(self) -> bool:
        return self.translation != self.machine_translation


class TranslationReviewWindow(Qw.QDialog, Ui_TranslationReview):
    """
    Review and edit the translations of the OCR output, page by page, next to the image.
    """

    images: list[imf.ImageFile]
    ocr_analytics: list[st.OCRAnalytic]  # Aligned with the images.
    pages: list[list[TranslationRow]]  # Aligned with the images.
    initial_translations: dict[Path, list[str]]

    translator_conf: cfg.TranslatorConfig
    api_key: str | None

    awaiting_user_input: bool
    first_load: bool
    worker_running: bool
    # Keep a reference to the running worker, otherwise its signals are garbage collected
    # before they can deliver the result.
    current_worker: wt.Worker | None

    state_saver: ss.StateSaver

    def __init__(
        self,
        parent,
        images: list[imf.ImageFile],
        ocr_analytics: list[st.OCRAnalytic],
        translations: dict[Path, list[str]],
        translator_conf: cfg.TranslatorConfig,
        api_key: str | None,
    ) -> None:
        """
        Init the window.

        :param parent: The parent widget.
        :param images: The loaded images. Pages are matched to them by path.
        :param ocr_analytics: The OCR results that were translated.
        :param translations: The translations per analytic path, one per bubble.
        :param translator_conf: The translator settings, used for translating again.
        :param api_key: The OpenRouter API key, used for translating again.
        """
        Qw.QDialog.__init__(self, parent)
        self.setupUi(self)

        self.translator_conf = translator_conf
        self.api_key = api_key
        self.initial_translations = {path: list(t) for path, t in translations.items()}
        self.awaiting_user_input = False
        self.first_load = True
        self.worker_running = False
        self.current_worker = None

        # Pair each page with its image. Pages without an image can't be shown,
        # but their translations are passed through unchanged.
        image_by_path = {image.path: image for image in images}
        pairs = []
        for analytic in ocr_analytics:
            image = image_by_path.get(analytic.path)
            if image is None:
                logger.warning(f"No loaded image for translated page {analytic.path}, skipping.")
                continue
            pairs.append((image, analytic))
        pairs = natsorted(pairs, key=lambda pair: pair[0].path)
        self.images = [image for image, _ in pairs]
        self.ocr_analytics = [analytic for _, analytic in pairs]
        logger.info(f"Opening Translation Review Window for {len(self.images)} pages.")

        self.pages = []
        for analytic in self.ocr_analytics:
            page_translations = translations.get(analytic.path, [])
            rows = []
            for index, (text, box) in enumerate(analytic.removed_box_data):
                translation = page_translations[index] if index < len(page_translations) else ""
                rows.append(TranslationRow(str(index + 1), box, text, translation, translation))
            self.pages.append(rows)

        self.tableWidget_translation.setEditableColumns([TRANSLATION_COLUMN])
        self.tableWidget_translation.setItemDelegate(WrapTextDelegate())
        self.tableWidget_translation.resized.connect(self.adjust_row_heights)
        self.tableWidget_translation.cellChanged.connect(self.handle_table_edited)
        self.tableWidget_translation.currentRowChanged.connect(self.update_image_boxes)
        self.tableWidget_translation.currentRowChanged.connect(self.update_button_availability)

        self.init_image_list()
        self.image_list.currentItemChanged.connect(self.handle_image_change)
        self.image_list.currentRowChanged.connect(self.check_arrow_buttons)
        self.image_list.verticalScrollBar().setSingleStep(120)
        self.pushButton_next.clicked.connect(
            lambda: self.image_list.setCurrentRow(self.image_list.currentRow() + 1)
        )
        self.pushButton_prev.clicked.connect(
            lambda: self.image_list.setCurrentRow(self.image_list.currentRow() - 1)
        )
        self.horizontalSlider_icon_size.valueChanged.connect(self.update_icon_size)
        self.horizontalSlider_icon_size.setValue(150)

        self.comboBox_view_mode.currentIndexChanged.connect(self.update_image_boxes)
        self.image_viewer.bubble_clicked.connect(self.handle_bubble_clicked)
        self.pushButton_zoom_in.clicked.connect(self.image_viewer.zoom_in)
        self.pushButton_zoom_out.clicked.connect(self.image_viewer.zoom_out)
        self.pushButton_zoom_fit.clicked.connect(self.image_viewer.zoom_fit)
        self.pushButton_zoom_reset.clicked.connect(self.image_viewer.zoom_reset)

        self.pushButton_retranslate_bubble.clicked.connect(
            partial(self.start_retranslation, single_bubble=True)
        )
        self.pushButton_retranslate_page.clicked.connect(
            partial(self.start_retranslation, single_bubble=False)
        )
        self.pushButton_reset.clicked.connect(self.reset_bubble)
        self.pushButton_add_glossary.clicked.connect(self.add_glossary_term)
        self.pushButton_done.clicked.connect(self.close)

        self.init_shortcuts()
        self.update_button_availability()

        # Give the table more room than in the OCR review, since it has two text columns.
        side_width = self.splitter_side.width()
        self.splitter_side.setSizes([side_width * 2 // 5, side_width * 3 // 5])
        self.tableWidget_translation.setColumnWidth(ORIGINAL_COLUMN, 250)

        self.state_saver = ss.StateSaver("translation_review")
        self.state_saver.register(self, self.splitter, self.splitter_side)
        self.state_saver.restore()

        if self.images:
            Qc.QTimer.singleShot(0, partial(self.image_list.setCurrentRow, 0))

    def init_shortcuts(self) -> None:
        def set_button_shortcut(button: Qw.QPushButton, key_sequence: Qg.QKeySequence) -> None:
            button.setShortcut(key_sequence)
            button.setToolTip(button.toolTip() + f" ({button.shortcut().toString()})")

        set_button_shortcut(self.pushButton_prev, Qg.QKeySequence(Qc.Qt.CTRL | Qc.Qt.Key_Left))
        set_button_shortcut(self.pushButton_next, Qg.QKeySequence(Qc.Qt.CTRL | Qc.Qt.Key_Right))
        set_button_shortcut(self.pushButton_reset, Qg.QKeySequence(Qc.Qt.CTRL | Qc.Qt.Key_R))
        set_button_shortcut(
            self.pushButton_retranslate_bubble, Qg.QKeySequence(Qc.Qt.CTRL | Qc.Qt.Key_T)
        )
        set_button_shortcut(
            self.pushButton_retranslate_page,
            Qg.QKeySequence(Qc.Qt.CTRL | Qc.Qt.SHIFT | Qc.Qt.Key_T),
        )
        set_button_shortcut(self.pushButton_add_glossary, Qg.QKeySequence(Qc.Qt.CTRL | Qc.Qt.Key_G))

    # Results =====================================================================================

    def get_final_translations(self) -> dict[Path, list[str]]:
        """
        Get the translations including the user's edits.
        Pages that weren't shown keep their original translations.

        :return: The translations per analytic path, one per bubble.
        """
        translations = {path: list(t) for path, t in self.initial_translations.items()}
        for analytic, rows in zip(self.ocr_analytics, self.pages):
            translations[analytic.path] = [row.translation for row in rows]
        return translations

    def has_changes(self) -> bool:
        """
        :return: True if any translation differs from what was loaded.
        """
        return self.get_final_translations() != self.initial_translations

    # Display =====================================================================================

    def current_rows(self) -> list[TranslationRow]:
        index = self.image_list.currentRow()
        if index < 0 or index >= len(self.pages):
            return []
        return self.pages[index]

    def switch_to_image(self, index: int) -> None:
        image = self.images[index]
        self.label_file_name.setText(str(image.path))
        self.label_file_name.setToolTip(str(image.path))
        self.label_file_name.setElideMode(Qc.Qt.ElideLeft)
        self.image_viewer.set_image(image.path)

        self.load_rows(self.pages[index])
        if self.tableWidget_translation.rowCount() > 0:
            self.tableWidget_translation.setCurrentCell(0, TRANSLATION_COLUMN)

        if self.first_load:
            Qc.QTimer.singleShot(0, self.image_viewer.zoom_fit)
            self.first_load = False

    @suppress_cell_update_handling
    def load_rows(self, rows: list[TranslationRow]) -> None:
        """
        Fill the table with the bubbles of one page.

        :param rows: The bubbles to show.
        """
        current_row = self.tableWidget_translation.currentRow()
        self.tableWidget_translation.clearAll()
        for index, row in enumerate(rows):
            self.tableWidget_translation.appendRow(row.label, row.text, row.translation)
            # Mark edited translations in italics.
            item = self.tableWidget_translation.item(index, TRANSLATION_COLUMN)
            font = item.font()
            font.setItalic(row.edited)
            item.setFont(font)
        if 0 <= current_row < len(rows):
            self.tableWidget_translation.setCurrentCell(current_row, TRANSLATION_COLUMN)
        self.update_image_boxes()
        self.adjust_row_heights()

    def adjust_row_heights(self) -> None:
        for row in range(self.tableWidget_translation.rowCount()):
            self.tableWidget_translation.resizeRowToContents(row)

    def update_image_boxes(self) -> None:
        """
        Draw the bubble boxes: green when translated, blue when edited,
        red when missing a translation, and highlighted when selected.
        """
        rows = self.current_rows()
        # View mode 1 is "Original", without boxes.
        if self.comboBox_view_mode.currentIndex() == 1 or not rows:
            self.image_viewer.clear_bubbles()
            return

        rects = [Qc.QRect(*row.box.as_tuple_xywh) for row in rows]
        colors = [
            COLOR_MISSING if not row.translation else COLOR_EDITED if row.edited else COLOR_NORMAL
            for row in rows
        ]
        labels = [row.label for row in rows]
        strokes = [Qc.Qt.SolidLine] * len(rows)

        selected_row = self.tableWidget_translation.currentRow()
        if 0 <= selected_row < len(rows):
            colors[selected_row] = self.palette().highlight().color()
        self.image_viewer.set_bubbles(rects, colors, labels, strokes)

    def update_button_availability(self) -> None:
        selected_row = self.tableWidget_translation.currentRow()
        rows = self.current_rows()
        has_selection = 0 <= selected_row < len(rows)
        idle = not self.worker_running
        self.pushButton_retranslate_bubble.setEnabled(idle and has_selection)
        self.pushButton_retranslate_page.setEnabled(idle and bool(rows))
        self.pushButton_reset.setEnabled(has_selection and rows[selected_row].edited)
        self.pushButton_add_glossary.setEnabled(has_selection)

    @Slot(int)
    def handle_bubble_clicked(self, index: int) -> None:
        self.tableWidget_translation.setCurrentCell(index, TRANSLATION_COLUMN)

    @Slot(int, int)
    def handle_table_edited(self, row: int, col: int) -> None:
        """
        Store the edited translation.

        :param row: The row of the edited cell.
        :param col: The column of the edited cell, only the translation column is editable.
        """
        if not self.awaiting_user_input or col != TRANSLATION_COLUMN:
            return
        rows = self.current_rows()
        if not 0 <= row < len(rows):
            return
        rows[row].translation = self.tableWidget_translation.item(row, col).text().strip()
        self.load_rows(rows)
        self.update_button_availability()

    def reset_bubble(self) -> None:
        """
        Undo the user's edit of the selected bubble.
        """
        rows = self.current_rows()
        selected_row = self.tableWidget_translation.currentRow()
        if not 0 <= selected_row < len(rows):
            return
        rows[selected_row].translation = rows[selected_row].machine_translation
        self.load_rows(rows)
        self.update_button_availability()

    # Translating again ===========================================================================

    def start_retranslation(self, single_bubble: bool) -> None:
        """
        Translate the current page again in a worker thread.
        The whole page is always sent, so the model has the context of the other bubbles.

        :param single_bubble: Only replace the selected bubble's translation.
            Otherwise, replace all bubbles the user didn't edit.
        """
        page_index = self.image_list.currentRow()
        rows = self.current_rows()
        if not rows:
            return
        only_row = None
        if single_bubble:
            only_row = self.tableWidget_translation.currentRow()
            if not 0 <= only_row < len(rows):
                return

        # Use the end of the previous page as context, like the batch translation does.
        previous_context = []
        if page_index > 0:
            previous_context = [
                (row.text, row.translation)
                for row in self.pages[page_index - 1]
                if row.text.strip() and row.translation
            ]

        worker = wt.Worker(
            trl.retranslate_page,
            self.translator_conf,
            self.api_key,
            self.images[page_index].path.name,
            [row.text for row in rows],
            previous_context,
            no_progress_callback=True,
        )
        worker.signals.result.connect(
            partial(self.retranslation_result, page_index=page_index, only_row=only_row)
        )
        worker.signals.error.connect(self.retranslation_error)
        worker.signals.finished.connect(self.retranslation_finished)

        self.worker_running = True
        self.current_worker = worker
        self.update_button_availability()
        Qw.QApplication.setOverrideCursor(Qc.Qt.WaitCursor)
        Qc.QThreadPool.globalInstance().start(worker)

    def retranslation_result(
        self, translations: list[str], page_index: int, only_row: int | None
    ) -> None:
        rows = self.pages[page_index]
        for index, (row, translation) in enumerate(zip(rows, translations)):
            if only_row is not None:
                if index == only_row:
                    row.translation = row.machine_translation = translation
            elif not row.edited:
                row.translation = row.machine_translation = translation
            else:
                # Keep the user's edit.
                pass
        if page_index == self.image_list.currentRow():
            self.load_rows(rows)

    def retranslation_error(self, error: wt.WorkerError) -> None:
        logger.error(f"Translation worker error: {error}")
        if isinstance(error.value, trl.TranslationError):
            gu.show_warning(self, self.tr("Translation Failed"), str(error.value))
        else:
            gu.show_exception(
                self, self.tr("Translation Failed"), self.tr("Encountered error:"), error
            )

    def retranslation_finished(self) -> None:
        Qw.QApplication.restoreOverrideCursor()
        self.worker_running = False
        self.current_worker = None
        self.update_button_availability()

    # Glossary ====================================================================================

    def add_glossary_term(self) -> None:
        """
        Ask for a term and add it to the profile's glossary file.
        """
        if not self.translator_conf.glossary_path:
            gu.show_warning(
                self,
                self.tr("No Glossary"),
                self.tr(
                    "No glossary file is set. Enter the path of a .csv or .json file as "
                    "Glossary Path in the Translator section of the profile first. "
                    "The file is created if it doesn't exist yet."
                ),
            )
            return

        rows = self.current_rows()
        selected_row = self.tableWidget_translation.currentRow()
        source, target = "", ""
        if 0 <= selected_row < len(rows):
            source = rows[selected_row].text
            target = rows[selected_row].translation

        dialog = GlossaryTermDialog(self, source, target)
        if dialog.exec() != Qw.QDialog.Accepted:
            return
        try:
            gl.add_glossary_entry(self.translator_conf.glossary_path, dialog.entry())
        except gl.GlossaryError as e:
            gu.show_warning(self, self.tr("Glossary Error"), str(e))
            return
        gu.show_info(
            self,
            self.tr("Term Added"),
            self.tr(
                "Added the term to {path}. It will be used the next time you translate."
            ).format(path=self.translator_conf.glossary_path),
        )

    # Image list ==================================================================================

    def init_image_list(self) -> None:
        window_width = self.width()
        self.splitter.setSizes([window_width // 4, 3 * window_width // 4])

        label_text = f_plural(len(self.images), self.tr("image"), self.tr("images"))
        self.label_image_count.setText(f"{len(self.images)} {label_text}")

        for image in self.images:
            item = Qw.QListWidgetItem(Qg.QIcon(str(image.path)), image.path.stem)
            self.image_list.addItem(item)

    @Slot(int)
    def update_icon_size(self, size: int) -> None:
        self.image_list.setIconSize(Qc.QSize(size, size))

    def check_arrow_buttons(self) -> None:
        current_row = self.image_list.currentRow()
        self.pushButton_prev.setEnabled(current_row > 0)
        self.pushButton_next.setEnabled(current_row < self.image_list.count() - 1)

    @Slot(Qw.QListWidgetItem, Qw.QListWidgetItem)
    def handle_image_change(
        self, current: Qw.QListWidgetItem = None, previous: Qw.QListWidgetItem = None
    ) -> None:
        index = self.image_list.currentRow()
        if 0 <= index < len(self.images):
            self.switch_to_image(index)
        self.update_button_availability()

    def closeEvent(self, event: Qg.QCloseEvent) -> None:
        if self.worker_running:
            gu.show_info(
                self,
                self.tr("Translating"),
                self.tr("Please wait until the current translation is finished."),
            )
            event.ignore()
            return
        if (
            gu.show_question(
                self,
                self.tr("Finish Review"),
                self.tr("Are you sure you want to finish the review?"),
            )
            == Qw.QMessageBox.Cancel
        ):
            event.ignore()
            return
        self.state_saver.save()
        event.accept()


class GlossaryTermDialog(Qw.QDialog):
    """
    A small form to enter a glossary term.
    """

    def __init__(self, parent, source: str, target: str) -> None:
        Qw.QDialog.__init__(self, parent)
        self.setWindowTitle(self.tr("Add to Glossary"))
        self.setMinimumWidth(450)

        layout = Qw.QVBoxLayout(self)
        hint = Qw.QLabel(
            self.tr(
                "Shorten the original text to just the term, e.g. a name, "
                "and enter how it must always be translated."
            )
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        form = Qw.QFormLayout()
        self.lineEdit_source = Qw.QLineEdit(source)
        self.lineEdit_target = Qw.QLineEdit(target)
        self.lineEdit_note = Qw.QLineEdit()
        self.lineEdit_note.setPlaceholderText(self.tr("Optional, e.g. main character, female"))
        form.addRow(self.tr("Original term:"), self.lineEdit_source)
        form.addRow(self.tr("Translation:"), self.lineEdit_target)
        form.addRow(self.tr("Note:"), self.lineEdit_note)
        layout.addLayout(form)

        self.buttons = Qw.QDialogButtonBox(Qw.QDialogButtonBox.Ok | Qw.QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.lineEdit_source.textChanged.connect(self.update_ok_button)
        self.lineEdit_target.textChanged.connect(self.update_ok_button)
        self.update_ok_button()
        self.lineEdit_source.setFocus()
        self.lineEdit_source.selectAll()

    def update_ok_button(self) -> None:
        self.buttons.button(Qw.QDialogButtonBox.Ok).setEnabled(
            bool(self.lineEdit_source.text().strip() and self.lineEdit_target.text().strip())
        )

    def entry(self) -> gl.GlossaryEntry:
        return gl.GlossaryEntry(
            self.lineEdit_source.text().strip(),
            self.lineEdit_target.text().strip(),
            self.lineEdit_note.text().strip(),
        )
