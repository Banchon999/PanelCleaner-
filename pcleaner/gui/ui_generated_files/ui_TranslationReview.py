# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'TranslationReview.ui'
##
## Created by: Qt User Interface Compiler version 6.11.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QDialog,
    QFrame, QHBoxLayout, QHeaderView, QLabel,
    QListView, QListWidget, QListWidgetItem, QPushButton,
    QSizePolicy, QSlider, QSpacerItem, QSplitter,
    QTableWidgetItem, QVBoxLayout, QWidget)

from pcleaner.gui.CustomQ.CElidedLabel import CElidedLabel
from pcleaner.gui.CustomQ.CTableWidget import CTableWidget
from pcleaner.gui.image_viewer import BubbleImageViewer

class Ui_TranslationReview(object):
    def setupUi(self, TranslationReview):
        if not TranslationReview.objectName():
            TranslationReview.setObjectName(u"TranslationReview")
        TranslationReview.resize(1400, 800)
        TranslationReview.setModal(True)
        self.verticalLayout_2 = QVBoxLayout(TranslationReview)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(1, 1, 1, 1)
        self.splitter = QSplitter(TranslationReview)
        self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Orientation.Horizontal)
        self.layoutWidget1 = QWidget(self.splitter)
        self.layoutWidget1.setObjectName(u"layoutWidget1")
        self.verticalLayout_3 = QVBoxLayout(self.layoutWidget1)
        self.verticalLayout_3.setSpacing(6)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(6, 6, 6, 7)
        self.label_image_count = QLabel(self.layoutWidget1)
        self.label_image_count.setObjectName(u"label_image_count")
        self.label_image_count.setText(u"<image count>")

        self.horizontalLayout_2.addWidget(self.label_image_count)

        self.horizontalSpacer = QSpacerItem(0, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_2.addItem(self.horizontalSpacer)

        self.label = QLabel(self.layoutWidget1)
        self.label.setObjectName(u"label")

        self.horizontalLayout_2.addWidget(self.label)

        self.horizontalSlider_icon_size = QSlider(self.layoutWidget1)
        self.horizontalSlider_icon_size.setObjectName(u"horizontalSlider_icon_size")
        self.horizontalSlider_icon_size.setMinimum(1)
        self.horizontalSlider_icon_size.setMaximum(1000)
        self.horizontalSlider_icon_size.setOrientation(Qt.Orientation.Horizontal)

        self.horizontalLayout_2.addWidget(self.horizontalSlider_icon_size)

        self.pushButton_prev = QPushButton(self.layoutWidget1)
        self.pushButton_prev.setObjectName(u"pushButton_prev")
        self.pushButton_prev.setText(u"")
        icon = QIcon(QIcon.fromTheme(u"arrow-left"))
        self.pushButton_prev.setIcon(icon)
        self.pushButton_prev.setFlat(True)

        self.horizontalLayout_2.addWidget(self.pushButton_prev)

        self.pushButton_next = QPushButton(self.layoutWidget1)
        self.pushButton_next.setObjectName(u"pushButton_next")
        self.pushButton_next.setText(u"")
        icon1 = QIcon(QIcon.fromTheme(u"arrow-right"))
        self.pushButton_next.setIcon(icon1)
        self.pushButton_next.setFlat(True)

        self.horizontalLayout_2.addWidget(self.pushButton_next)

        self.horizontalLayout_2.setStretch(1, 1)
        self.horizontalLayout_2.setStretch(3, 3)

        self.verticalLayout_3.addLayout(self.horizontalLayout_2)

        self.image_list = QListWidget(self.layoutWidget1)
        self.image_list.setObjectName(u"image_list")
        self.image_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.image_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.image_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.image_list.setProperty(u"showDropIndicator", False)
        self.image_list.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self.image_list.setTextElideMode(Qt.TextElideMode.ElideLeft)
        self.image_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.image_list.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.image_list.setMovement(QListView.Movement.Static)
        self.image_list.setFlow(QListView.Flow.LeftToRight)
        self.image_list.setProperty(u"isWrapping", True)
        self.image_list.setResizeMode(QListView.ResizeMode.Adjust)
        self.image_list.setLayoutMode(QListView.LayoutMode.Batched)
        self.image_list.setViewMode(QListView.ViewMode.IconMode)
        self.image_list.setUniformItemSizes(False)
        self.image_list.setBatchSize(50)
        self.image_list.setWordWrap(False)
        self.image_list.setSelectionRectVisible(True)

        self.verticalLayout_3.addWidget(self.image_list)

        self.splitter.addWidget(self.layoutWidget1)
        self.layoutWidget = QWidget(self.splitter)
        self.layoutWidget.setObjectName(u"layoutWidget")
        self.verticalLayout = QVBoxLayout(self.layoutWidget)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setSpacing(6)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(6, 6, 6, 6)
        self.label_file_name = CElidedLabel(self.layoutWidget)
        self.label_file_name.setObjectName(u"label_file_name")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_file_name.sizePolicy().hasHeightForWidth())
        self.label_file_name.setSizePolicy(sizePolicy)
        self.label_file_name.setFrameShape(QFrame.Shape.NoFrame)
        self.label_file_name.setFrameShadow(QFrame.Shadow.Raised)

        self.horizontalLayout.addWidget(self.label_file_name)

        self.pushButton_zoom_in = QPushButton(self.layoutWidget)
        self.pushButton_zoom_in.setObjectName(u"pushButton_zoom_in")
        icon2 = QIcon(QIcon.fromTheme(u"zoom-in"))
        self.pushButton_zoom_in.setIcon(icon2)
        self.pushButton_zoom_in.setFlat(True)

        self.horizontalLayout.addWidget(self.pushButton_zoom_in)

        self.pushButton_zoom_out = QPushButton(self.layoutWidget)
        self.pushButton_zoom_out.setObjectName(u"pushButton_zoom_out")
        icon3 = QIcon(QIcon.fromTheme(u"zoom-out"))
        self.pushButton_zoom_out.setIcon(icon3)
        self.pushButton_zoom_out.setFlat(True)

        self.horizontalLayout.addWidget(self.pushButton_zoom_out)

        self.pushButton_zoom_reset = QPushButton(self.layoutWidget)
        self.pushButton_zoom_reset.setObjectName(u"pushButton_zoom_reset")
        icon4 = QIcon(QIcon.fromTheme(u"zoom-original"))
        self.pushButton_zoom_reset.setIcon(icon4)
        self.pushButton_zoom_reset.setFlat(True)

        self.horizontalLayout.addWidget(self.pushButton_zoom_reset)

        self.pushButton_zoom_fit = QPushButton(self.layoutWidget)
        self.pushButton_zoom_fit.setObjectName(u"pushButton_zoom_fit")
        icon5 = QIcon(QIcon.fromTheme(u"zoom-fit-best"))
        self.pushButton_zoom_fit.setIcon(icon5)
        self.pushButton_zoom_fit.setFlat(True)

        self.horizontalLayout.addWidget(self.pushButton_zoom_fit)

        self.comboBox_view_mode = QComboBox(self.layoutWidget)
        self.comboBox_view_mode.addItem("")
        self.comboBox_view_mode.addItem("")
        self.comboBox_view_mode.setObjectName(u"comboBox_view_mode")

        self.horizontalLayout.addWidget(self.comboBox_view_mode)

        self.line = QFrame(self.layoutWidget)
        self.line.setObjectName(u"line")
        self.line.setFrameShape(QFrame.Shape.VLine)
        self.line.setFrameShadow(QFrame.Shadow.Sunken)

        self.horizontalLayout.addWidget(self.line)

        self.pushButton_retranslate_bubble = QPushButton(self.layoutWidget)
        self.pushButton_retranslate_bubble.setObjectName(u"pushButton_retranslate_bubble")
        icon6 = QIcon(QIcon.fromTheme(u"view-refresh"))
        self.pushButton_retranslate_bubble.setIcon(icon6)
        self.pushButton_retranslate_bubble.setFlat(True)

        self.horizontalLayout.addWidget(self.pushButton_retranslate_bubble)

        self.pushButton_retranslate_page = QPushButton(self.layoutWidget)
        self.pushButton_retranslate_page.setObjectName(u"pushButton_retranslate_page")
        self.pushButton_retranslate_page.setIcon(icon6)
        self.pushButton_retranslate_page.setFlat(True)

        self.horizontalLayout.addWidget(self.pushButton_retranslate_page)

        self.pushButton_reset = QPushButton(self.layoutWidget)
        self.pushButton_reset.setObjectName(u"pushButton_reset")
        self.pushButton_reset.setText(u"")
        icon7 = QIcon(QIcon.fromTheme(u"edit-reset"))
        self.pushButton_reset.setIcon(icon7)
        self.pushButton_reset.setFlat(True)

        self.horizontalLayout.addWidget(self.pushButton_reset)

        self.line_2 = QFrame(self.layoutWidget)
        self.line_2.setObjectName(u"line_2")
        self.line_2.setFrameShape(QFrame.Shape.VLine)
        self.line_2.setFrameShadow(QFrame.Shadow.Sunken)

        self.horizontalLayout.addWidget(self.line_2)

        self.pushButton_add_glossary = QPushButton(self.layoutWidget)
        self.pushButton_add_glossary.setObjectName(u"pushButton_add_glossary")
        icon8 = QIcon(QIcon.fromTheme(u"bookmark-new"))
        self.pushButton_add_glossary.setIcon(icon8)
        self.pushButton_add_glossary.setFlat(True)

        self.horizontalLayout.addWidget(self.pushButton_add_glossary)

        self.line_3 = QFrame(self.layoutWidget)
        self.line_3.setObjectName(u"line_3")
        self.line_3.setFrameShape(QFrame.Shape.VLine)
        self.line_3.setFrameShadow(QFrame.Shadow.Sunken)

        self.horizontalLayout.addWidget(self.line_3)

        self.pushButton_done = QPushButton(self.layoutWidget)
        self.pushButton_done.setObjectName(u"pushButton_done")

        self.horizontalLayout.addWidget(self.pushButton_done)

        self.horizontalLayout.setStretch(0, 1)

        self.verticalLayout.addLayout(self.horizontalLayout)

        self.splitter_side = QSplitter(self.layoutWidget)
        self.splitter_side.setObjectName(u"splitter_side")
        self.splitter_side.setOrientation(Qt.Orientation.Horizontal)
        self.image_viewer = BubbleImageViewer(self.splitter_side)
        self.image_viewer.setObjectName(u"image_viewer")
        self.splitter_side.addWidget(self.image_viewer)
        self.tableWidget_translation = CTableWidget(self.splitter_side)
        if (self.tableWidget_translation.columnCount() < 3):
            self.tableWidget_translation.setColumnCount(3)
        __qtablewidgetitem = QTableWidgetItem()
        self.tableWidget_translation.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.tableWidget_translation.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.tableWidget_translation.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        self.tableWidget_translation.setObjectName(u"tableWidget_translation")
        self.tableWidget_translation.setAcceptDrops(True)
        self.tableWidget_translation.setEditTriggers(QAbstractItemView.EditTrigger.AllEditTriggers)
        self.tableWidget_translation.setTabKeyNavigation(False)
        self.tableWidget_translation.setProperty(u"showDropIndicator", True)
        self.tableWidget_translation.setDragEnabled(True)
        self.tableWidget_translation.setDragDropOverwriteMode(False)
        self.tableWidget_translation.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self.tableWidget_translation.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.tableWidget_translation.setAlternatingRowColors(True)
        self.tableWidget_translation.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tableWidget_translation.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.splitter_side.addWidget(self.tableWidget_translation)
        self.tableWidget_translation.horizontalHeader().setDefaultSectionSize(80)
        self.tableWidget_translation.horizontalHeader().setStretchLastSection(True)
        self.tableWidget_translation.verticalHeader().setVisible(False)

        self.verticalLayout.addWidget(self.splitter_side)

        self.verticalLayout.setStretch(1, 1)
        self.splitter.addWidget(self.layoutWidget)

        self.verticalLayout_2.addWidget(self.splitter)


        self.retranslateUi(TranslationReview)

        QMetaObject.connectSlotsByName(TranslationReview)
    # setupUi

    def retranslateUi(self, TranslationReview):
        TranslationReview.setWindowTitle(QCoreApplication.translate("TranslationReview", u"Review Translation", None))
        self.label.setText(QCoreApplication.translate("TranslationReview", u"Icon Size:", None))
#if QT_CONFIG(tooltip)
        self.pushButton_prev.setToolTip(QCoreApplication.translate("TranslationReview", u"Previous image", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(tooltip)
        self.pushButton_next.setToolTip(QCoreApplication.translate("TranslationReview", u"Next image", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(tooltip)
        self.pushButton_zoom_in.setToolTip(QCoreApplication.translate("TranslationReview", u"Zoom in", None))
#endif // QT_CONFIG(tooltip)
        self.pushButton_zoom_in.setText("")
#if QT_CONFIG(tooltip)
        self.pushButton_zoom_out.setToolTip(QCoreApplication.translate("TranslationReview", u"Zoom out", None))
#endif // QT_CONFIG(tooltip)
        self.pushButton_zoom_out.setText("")
#if QT_CONFIG(tooltip)
        self.pushButton_zoom_reset.setToolTip(QCoreApplication.translate("TranslationReview", u"Reset zoom", None))
#endif // QT_CONFIG(tooltip)
        self.pushButton_zoom_reset.setText("")
#if QT_CONFIG(tooltip)
        self.pushButton_zoom_fit.setToolTip(QCoreApplication.translate("TranslationReview", u"Zoom to fit", None))
#endif // QT_CONFIG(tooltip)
        self.pushButton_zoom_fit.setText("")
        self.comboBox_view_mode.setItemText(0, QCoreApplication.translate("TranslationReview", u"With Boxes", None))
        self.comboBox_view_mode.setItemText(1, QCoreApplication.translate("TranslationReview", u"Original", None))

#if QT_CONFIG(tooltip)
        self.pushButton_retranslate_bubble.setToolTip(QCoreApplication.translate("TranslationReview", u"Translate the selected bubble again", None))
#endif // QT_CONFIG(tooltip)
        self.pushButton_retranslate_bubble.setText(QCoreApplication.translate("TranslationReview", u"Retranslate Bubble", None))
#if QT_CONFIG(tooltip)
        self.pushButton_retranslate_page.setToolTip(QCoreApplication.translate("TranslationReview", u"Translate all bubbles on this page again, except the ones you edited", None))
#endif // QT_CONFIG(tooltip)
        self.pushButton_retranslate_page.setText(QCoreApplication.translate("TranslationReview", u"Retranslate Page", None))
#if QT_CONFIG(tooltip)
        self.pushButton_reset.setToolTip(QCoreApplication.translate("TranslationReview", u"Undo your edit of the selected bubble", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(tooltip)
        self.pushButton_add_glossary.setToolTip(QCoreApplication.translate("TranslationReview", u"Add a term to the glossary, so it is always translated the same way", None))
#endif // QT_CONFIG(tooltip)
        self.pushButton_add_glossary.setText(QCoreApplication.translate("TranslationReview", u"Add to Glossary", None))
        self.pushButton_done.setText(QCoreApplication.translate("TranslationReview", u"Done", None))
        ___qtablewidgetitem = self.tableWidget_translation.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("TranslationReview", u"Box", None))
        ___qtablewidgetitem1 = self.tableWidget_translation.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("TranslationReview", u"Original", None))
        ___qtablewidgetitem2 = self.tableWidget_translation.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("TranslationReview", u"Translation", None))
    # retranslateUi

