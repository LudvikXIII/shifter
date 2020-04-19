# -*- coding: utf-8 -*-
# Standard
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import
from __future__ import generators
from __future__ import division
# copystandard
import os
import copy
import pprint

# dcc
import maya.cmds as cmds

# mgear
from mgear.core import pyqt
from mgear.core import callbackManager
from mgear.shifter import io
from mgear.shifter import afg_tools
# from mgear.vendor.Qt import QtCore
# from mgear.vendor.Qt import QtWidgets
from PySide2 import QtCore
from PySide2 import QtWidgets

reload(pyqt)
reload(afg_tools)

# constants -------------------------------------------------------------------
WINDOW_TITLE = "Auto Fit Guide Tools (AFG)"


def get_top_level_widgets(class_name=None, object_name=None):
    """
    Get existing widgets for a given class name

    Args:
        class_name (str): Name of class to search top level widgets for
        object_name (str): Qt object name

    Returns:
        List of QWidgets
    """
    matches = []

    # Find top level widgets matching class name
    for widget in QtWidgets.QApplication.topLevelWidgets():
        try:
            # Matching class
            if class_name and widget.metaObject().className() == class_name:
                matches.append(widget)
            # Matching object name
            elif object_name and widget.objectName() == object_name:
                matches.append(widget)
        except AttributeError:
            continue
        # Print unhandled to the shell
        except Exception as e:
            print(e)

    return matches


def close_existing(class_name=None, object_name=None):
    """
    Close and delete any existing windows of class_name

    Args:
        class_name (str): QtWidget class name
        object_name (str): Qt object name

    Returns: None
    """
    for widget in get_top_level_widgets(class_name, object_name):
        # Close
        widget.close()
        # Delete
        widget.deleteLater()


def show(*args):
    try:
        close_existing(class_name="AutoFitGuideTool",
                       object_name="AutoFitGuideTool")
    except Exception:
        pass
    maya_window = pyqt.maya_main_window() or None
    AFG_TOOL_UI = AutoFitGuideTool(parent=maya_window)
    AFG_TOOL_UI.show()
    return AFG_TOOL_UI


def fileDialog(startDir, ext=None, mode=0):
    """prompt dialog for either import/export from a UI

    Args:
        startDir (str): A directory to start from
        mode (int, optional): import or export, 0/1

    Returns:
        str: path selected by user
    """

    fPath = cmds.fileDialog2(dialogStyle=2,
                             fileMode=mode,
                             startingDirectory=startDir,
                             fileFilter=ext)
    if fPath is not None:
        fPath = fPath[0]
    return fPath


class PathObjectExistsEdit(QtWidgets.QLineEdit):
    """docstring for PathObjectExistsEdit"""
    focusedIn = QtCore.Signal()

    def __init__(self,
                 default_value=None,
                 text=None,
                 placeholderText=None,
                 validate_mode='path',
                 parent=None):
        super(PathObjectExistsEdit, self).__init__(text=text,
                                                   placeholderText=placeholderText,
                                                   parent=parent)
        # self.validate_types = {'path': self.validatePath,
        #                        'mayaExists': self.validateNodeExists}
        self.validate_mode = validate_mode
        self.export_path = False
        self.setDefaultValue(default_value)
        self.editingFinished.connect(self.visualizeValidation)
        self.editingFinished.connect(self.selectMayaNode)

    def setNeutral(self):
        self.setStyleSheet('')

    def setDefaultValue(self, default_value):
        if default_value is None:
            self.default_value = None
            return
        self.default_value = '[{}]'.format(default_value)
        self.setText(self.default_value)
        completer = QtWidgets.QCompleter([self.default_value])
        completer.setFilterMode(QtCore.Qt.MatchContains)
        self.setCompleter(completer)

    def setValid(self):
        self.setStyleSheet('border: 1px solid green;')

    def setInvalid(self):
        self.setStyleSheet('border: 1px solid red;')

    def selectMayaNode(self):
        if self.validate_mode == 'mayaExists' and self.validateNodeExists:
            if self.text() == '':
                return
            cmds.select(cl=True)
            cmds.select(self.text())

    def visualizeValidation(self):
        text = self.text()
        if text.replace(' ', '') == '' or text == '' or text.replace(' ', '') == self.default_value:
            self.setNeutral()
            return

        if self.validate_mode == 'path' and self.validatePath():
            self.setValid()
        elif self.validate_mode == 'path' and not self.validatePath():
            self.setInvalid()
        elif self.validate_mode == 'mayaExists' and self.validateNodeExists():
            self.setValid()
        elif self.validate_mode == 'mayaExists' and not self.validateNodeExists():
            self.setInvalid()

    def validateNodeExists(self):
        return cmds.objExists(self.text())

    def validatePath(self):
        validated = os.path.exists(self.text())
        if self.export_path:
            validated = True
        return validated

    def focusInEvent(self, event):
        self.focusedIn.emit()
        super(PathObjectExistsEdit, self).focusInEvent(event)


class SelectComboBoxRefreshWidget(QtWidgets.QWidget):
    """docstring for SelectComboBoxRefreshWidget"""
    def __init__(self, label_text, default_value=None, parent=None):
        super(SelectComboBoxRefreshWidget, self).__init__(parent=parent)
        self.mainLayout = QtWidgets.QHBoxLayout()
        self.setLayout(self.mainLayout)
        self.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setSpacing(0)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)

        self.selected_mesh_ledit = PathObjectExistsEdit(text=None,
                                                        default_value=default_value,
                                                        validate_mode='mayaExists',
                                                        placeholderText='Enter Mesh Name...')
        self.selected_mesh_ledit.setMinimumHeight(24 + 2)
        style = QtWidgets.QStyle
        self.refresh_btn = QtWidgets.QPushButton()
        self.refresh_btn.setIcon(self.style().standardIcon(getattr(style, 'SP_BrowserReload')))
        # self.refresh_btn.setIcon(pyqt.get_icon("refresh-ccw"))
        self.refresh_btn.setMinimumHeight(24)
        self.refresh_btn.setMaximumHeight(24)
        self.refresh_btn.setMinimumWidth(24)
        self.refresh_btn.setMaximumWidth(24)
        self.mainLayout.addWidget(QtWidgets.QLabel(label_text))
        self.mainLayout.addWidget(self.selected_mesh_ledit, 1)
        self.mainLayout.addWidget(self.refresh_btn)

        self.refreshMeshList()
        self.connectSignals()

    def connectSignals(self):
        self.refresh_btn.clicked.connect(self.refreshMeshList)
        self.selected_mesh_ledit.focusedIn.connect(self.refreshMeshList)

    def refreshMeshList(self):
        # self.selected_mesh_ledit.clear()
        items = list(set(cmds.ls(exactType="mesh")))
        items.sort()
        completer = QtWidgets.QCompleter(items)
        completer.setFilterMode(QtCore.Qt.MatchContains)
        self.selected_mesh_ledit.setCompleter(completer)
        self.selected_mesh_ledit.setNeutral()

    @property
    def text(self):
        return self.selected_mesh_ledit.text()


class LoadImportWidget(QtWidgets.QWidget):
    """docstring for LoadImportWidget"""
    def __init__(self,
                 file_contents=None,
                 ext=None,
                 import_type="maya",
                 show_import_button=True,
                 parent=None):
        super(LoadImportWidget, self).__init__(parent=parent)
        self.import_type = import_type
        self.ext = ext
        self.mainLayout = QtWidgets.QHBoxLayout()
        self.mainLayout.setSpacing(0)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.mainLayout)
        if file_contents:
            button_label = 'Import {}'.format(file_contents)
            placeholderText = 'Path to {} file...'.format(file_contents)
        else:
            button_label = 'Import'
            placeholderText = 'Path to file...'
        self.path_widget = PathObjectExistsEdit(placeholderText=placeholderText)
        self.load_button = QtWidgets.QPushButton("...")
        self.import_button = QtWidgets.QPushButton(button_label)
        self.import_button.setMinimumWidth(100)
        if not show_import_button:
            self.import_button.hide()

        self.mainLayout.addWidget(self.path_widget, 1)
        self.mainLayout.addWidget(self.load_button, 0)
        self.mainLayout.addWidget(self.import_button, 0)
        self.path_widget.setMinimumHeight(24)
        self.load_button.setMinimumHeight(24)
        self.import_button.setMinimumHeight(24)
        self.connectSignals()

    def connectSignals(self):
        self.load_button.clicked.connect(self.loadPathDialog)
        self.import_button.clicked.connect(self._import)

    def _import(self):
        if self.path_widget.text().replace(' ', '') == '':
            return
        if self.import_type == 'maya':
            cmds.file(self.path_widget.text(), i=True)
        elif self.import_type == 'mgear':
            io.import_guide_template(filePath=self.path_widget.text())

    def loadPathDialog(self):
        # multipleFilters = "Maya Files (*.ma *.mb);;Maya ASCII (*.ma);;Maya Binary (*.mb);;All Files (*.*)"
        if self.ext:
            tmp = ' '.join(['*.{}'.format(x) for x in self.ext])
            all_exts = ['AFG Files ({})'.format(tmp), 'All Files (*.*)']
            all_exts = ';;'.join(all_exts)
        file_path = fileDialog("/", ext=all_exts, mode=1)
        if file_path:
            self.path_widget.setText(file_path)
        self.path_widget.visualizeValidation()

    @property
    def path(self):
        return self.path_widget.text()


class AutoFitBipedWidget(QtWidgets.QWidget):
    """docstring for AutoFitBipedWidget"""
    def __init__(self, parent=None):
        super(AutoFitBipedWidget, self).__init__(parent=parent)
        self.afb_cb_manager = callbackManager.CallbackManager()
        self.window().afg_callback_managers.append(self.afb_cb_manager)
        self.model_path = None
        self.guide_path = None
        self.setWindowTitle("Auto Fit Biped")
        self.mainLayout = QtWidgets.QVBoxLayout()
        self.setLayout(self.mainLayout)
        self.mainLayout.addWidget(self.embedSettingsInfoWidget())
        self.mainLayout.addWidget(self.exportEmbedInfoWidget())
        self.__isInteractiveEnabled = False
        self.connectSignals()

    def connectSignals(self):
        self.default_association_cb.toggled.connect(self.setAssociationWidget)
        self.run_all_settings_btn.clicked.connect(self.runAllEmbed)
        self.smart_adjust_btn.clicked.connect(self.runSmartAdjust)
        self.mirror_embed_btns.clicked.connect(self.runMirrorEmbed)
        self.match_guides_toEmbed_btn.clicked.connect(self.matchGuidesToEmbedOutput)
        self.create_embed_nodes_btn.clicked.connect(self.createEmbedNodes)
        self.src_geo_widget.selected_mesh_ledit.editingFinished.connect(self._updateStoredEmbedInfo)
        # create/export -------------------------------------------------------
        self.association_list_widget.currentRowChanged.connect(self.selectAssociationListItem)
        self.enable_association_btn.toggled.connect(self._interactiveToggled)
        self.mirror_association_btn.clicked.connect(self._mirrorAssociationInfo)
        self.clear_association_btn.clicked.connect(self._clearUserAssociations)
        self.print_association_btn.clicked.connect(self._printUserAssociation)

    def setAssociationWidget(self, *args):
        self.import_association_path_widget.setEnabled(not(self.default_association_cb.isChecked()))

    def getGuideAssociationInfo(self):
        embed_path = self.import_association_path_widget.path
        if self.default_association_cb.isChecked():
            return copy.deepcopy(afg_tools.DEFAULT_EMBED_GUIDE_ASSOCIATION)
        else:
            return afg_tools._importData(embed_path)

    def _getMirrorSide(self):
        mirror_embed_side = 'left'
        if self.mirror_none_rbtn.isChecked():
            mirror_embed_side = False
        elif self.mirror_right_rbtn.isChecked():
            mirror_embed_side = 'right'
        return mirror_embed_side

    def createEmbedNodes(self):
        self.safetyChecksRun()
        embed_info = self.getEmbedInfo()
        afg_tools.createNodeFromEmbedInfo(embed_info)
        # self._updateStoredEmbedInfo(embed_info=embed_info)

    def matchGuidesToEmbedOutput(self):
        guide_association_info = self.getGuideAssociationInfo()
        if self.enable_adjust_rbtn.isChecked():
            afg_tools.matchGuidesToEmbedOutput(guide_association_info=guide_association_info,
                                               guide_root=afg_tools.GUIDE_ROOT_NAME,
                                               setup_geo=self.src_geo_widget.text,
                                               scale_guides=True,
                                               manual_scale=False,
                                               lowest_point_node=None,
                                               min_height_nodes=None,
                                               adjust_hand_position=True,
                                               orient_adjust_arms=True)
        else:
            afg_tools.simpleMatchGuideToEmbed(guide_association_info)

    def runMirrorEmbed(self):
        if not self._getMirrorSide():
            return
        afg_tools.mirrorEmbedNodesSide(search=self._getMirrorSide(),
                                       replace=afg_tools.SIDE_MIRROR_INFO[self._getMirrorSide()])

    def runSmartAdjust(self):
        afg_tools.smartAdjustEmbedOutput(make_limbs_planar=True,
                                         mirror_side=True,
                                         favor_side=self._getMirrorSide(),
                                         center_hips=True,
                                         align_spine=True,
                                         adjust_Back_pos=True,
                                         spine_blend=.6,
                                         spine_height_only=True)

    def safetyChecksRun(self):
        if self.model_path.path == '' and not cmds.objExists(self.src_geo_widget.text):
            msg = 'No Source geometry supplied!'
            cmds.warning(msg)
            self.window().statusBar().showMessage(msg, 3000)
            return False
        elif self.model_path.path != '' and not cmds.objExists(self.src_geo_widget.text):
            msg = 'No Source geometry supplied!'
            cmds.warning(msg)
            self.window().statusBar().showMessage(msg, 3000)
            self.src_geo_widget.selected_mesh_ledit.setFocus()
            return False

        if self.guide_path.path == '' and not cmds.objExists(afg_tools.GUIDE_ROOT_NAME):
            msg = 'No Guide path or node supplied!'
            cmds.warning(msg)
            self.window().statusBar().showMessage(msg, 3000)
            return False
        if not self.default_association_cb.isChecked() and self.import_association_path_widget.path == '':
            msg = 'No Association info supplied! Either filepath or Default'
            cmds.warning(msg)
            self.window().statusBar().showMessage(msg, 3000)
            self.import_association_path_widget.path_widget.setFocus()
            return False
        return True

    def _updateStoredEmbedInfo(self, embed_info=None):
        self.storedEmbedInfo = {}
        self.storedEmbedInfo[self.src_geo_widget.text] = embed_info

    def _getEmbedInfo(self):
        embed_info = afg_tools.getEmbedInfoFromShape(self.src_geo_widget.text,
                                                     segmentationMethod=self.embed_options_cbb.currentIndex(),
                                                     segmentationResolution=int(self.embed_rez_cbb.currentText()))
        return embed_info

    def getEmbedInfo(self):
        embed_info = self.storedEmbedInfo.get(self.src_geo_widget.text, {})
        if not embed_info:
            embed_info = self._getEmbedInfo()
            self._updateStoredEmbedInfo(embed_info)
        return embed_info

    def runAllEmbed(self):

        if not self.safetyChecksRun():
            return
        smart_adjust = self.enable_adjust_rbtn.isChecked()

        if self.model_path.path:
            self.model_path._import()
        if self.guide_path.path and not cmds.objExists(afg_tools.GUIDE_ROOT_NAME):
            self.guide_path._import()

        embed_info = afg_tools.runAllEmbed(self.getGuideAssociationInfo(),
                                           self.src_geo_widget.text,
                                           afg_tools.GUIDE_ROOT_NAME,
                                           segmentationMethod=self.embed_options_cbb.currentIndex(),
                                           segmentationResolution=int(self.embed_rez_cbb.currentText()),
                                           scale_guides=True,
                                           lowest_point_node=None,
                                           min_height_nodes=None,
                                           smart_adjust=smart_adjust,
                                           adjust_hand_position=smart_adjust,
                                           orient_adjust_arms=smart_adjust,
                                           mirror_embed_side=self._getMirrorSide())
        self._updateStoredEmbedInfo(embed_info)


    # create/export function --------------------------------------------------
    def _printUserAssociation(self):
        pprint.pprint(afg_tools.INTERACTIVE_ASSOCIATION_INFO)

    def _mirrorAssociationInfo(self):
        afg_tools.mirrorInteractiveAssociation()
        self.visualizeAssociationEntry()

    def _clearUserAssociations(self):
        print(afg_tools.INTERACTIVE_ASSOCIATION_INFO)
        afg_tools.clearUserAssociations()
        self.visualizeAssociationEntry()

    def _interactiveToggled(self):
        if self.__isInteractiveEnabled:
            self.endInteractiveAssociation()
            self.__isInteractiveEnabled = False
            self.enable_association_btn.setText("Enable\nInteractive Association")

        else:
            self.startInteractiveAssociation()
            self.__isInteractiveEnabled = True
            self.enable_association_btn.setText("Disable\nInteractive Association")

    def updateInteractiveAssociation(self, *args):
        afg_tools.interactiveAssociation(matchTransform=False)
        self.visualizeAssociationEntry()

    def startInteractiveAssociation(self):
        self.afb_cb_manager.selectionChangedCB('interactive_association',
                                               self.updateInteractiveAssociation)

    def endInteractiveAssociation(self):
        self.afb_cb_manager.removeManagedCB('interactive_association')

    def visualizeAssociationEntry(self):
        for index in xrange(self.association_list_widget.count()):
            item = self.association_list_widget.item(index)
            embed_name = item.text()
            font = item.font()
            if embed_name in afg_tools.INTERACTIVE_ASSOCIATION_INFO:
                font.setItalic(True)
            else:
                font.setItalic(False)
            item.setFont(font)

    def selectAssociationListItem(self, *args):
        item = self.association_list_widget.currentItem()
        if not item:
            return
        item = item.text()
        if not cmds.objExists(item):
            return
        if item in afg_tools.INTERACTIVE_ASSOCIATION_INFO:
            items = [item]
            items.extend(afg_tools.INTERACTIVE_ASSOCIATION_INFO[item])
        else:
            items = [item]
        cmds.select(items)

    def embedSettingsInfoWidget(self):
        widget = QtWidgets.QGroupBox('Embed Node Settings')
        layout = QtWidgets.QVBoxLayout()
        layout.setAlignment(QtCore.Qt.AlignTop)
        widget.setLayout(layout)
        association_layout = QtWidgets.QHBoxLayout()
        self.default_association_cb = QtWidgets.QCheckBox('Use Default')
        self.default_association_cb.setChecked(True)
        self.import_association_path_widget = LoadImportWidget(file_contents='Biped Association Info',
                                                               ext=['afg'],
                                                               show_import_button=False)
        self.import_association_path_widget.setEnabled(False)
        association_layout.addWidget(self.default_association_cb)
        association_layout.addWidget(self.import_association_path_widget)
        self.import_association_path_widget.load_button.setMinimumWidth(24)
        self.src_geo_widget = SelectComboBoxRefreshWidget("Source Mesh    ")

        # embed options ------------------------------------------------------
        h_layout_01 = QtWidgets.QHBoxLayout()
        label_01 = QtWidgets.QLabel('Embed Resolution')
        self.embed_rez_cbb = QtWidgets.QComboBox()
        self.embed_rez_cbb.addItems(['64', '128', '512', '1024'])
        self.embed_rez_cbb.setCurrentIndex(1)
        self.embed_rez_cbb.setMinimumHeight(24 + 2)
        self.embed_rez_cbb.setMinimumWidth(150)
        self.embed_rez_cbb.setStyleSheet('background-color: transparent; QComboBox::down-arrow:on { top: 1px; left: 1px;};')
        h_layout_01.addWidget(label_01)
        h_layout_01.insertStretch(1, 1)
        h_layout_01.addWidget(self.embed_rez_cbb, 1)

        h_layout_02 = QtWidgets.QHBoxLayout()
        label_02 = QtWidgets.QLabel('Embed type')
        self.embed_options_cbb = QtWidgets.QComboBox()
        self.embed_options_cbb.addItems(['Perfect Mesh', 'Watertight Mesh ', 'Imperfect mesh', 'Polygon Repair'])
        self.embed_options_cbb.setStyleSheet('background-color: transparent;')
        self.embed_options_cbb.setCurrentIndex(3)
        self.embed_options_cbb.setMinimumHeight(24 + 2)
        self.embed_options_cbb.setMinimumWidth(150)
        h_layout_02.addWidget(label_02)
        h_layout_02.insertStretch(1, 1)
        h_layout_02.addWidget(self.embed_options_cbb, 1)
        #  ----------------------------------------------------------------
        mirror_radio_layout = QtWidgets.QHBoxLayout()
        radio_label = QtWidgets.QLabel('Mirror Embed Nodes')
        self.mirror_left_rbtn = QtWidgets.QRadioButton('Left')
        self.mirror_left_rbtn.setChecked(True)
        self.mirror_right_rbtn = QtWidgets.QRadioButton('Right')
        self.mirror_none_rbtn = QtWidgets.QRadioButton('None')
        self.mirror_embed_btns = QtWidgets.QPushButton('Run')
        self.mirror_embed_btns.setMaximumWidth(30)
        mirror_radio_layout.addWidget(radio_label)
        mirror_radio_layout.insertStretch(1, 1)
        mirror_radio_layout.addWidget(self.mirror_left_rbtn, 1)
        mirror_radio_layout.addWidget(self.mirror_none_rbtn, 1)
        mirror_radio_layout.addWidget(self.mirror_right_rbtn, 1)
        mirror_radio_layout.addWidget(self.mirror_embed_btns)
        mirror_rbtn_group = QtWidgets.QButtonGroup()
        mirror_rbtn_group.setObjectName('mirror_rbtn_group')
        mirror_rbtn_group.setExclusive(True)
        mirror_rbtn_group.addButton(self.mirror_left_rbtn)
        mirror_rbtn_group.addButton(self.mirror_none_rbtn)
        mirror_rbtn_group.addButton(self.mirror_right_rbtn)
        mirror_rbtn_group.setParent(mirror_radio_layout)

        #  --------------------------------------------------------------------
        smart_adjust_layout = QtWidgets.QHBoxLayout()
        smart_label = QtWidgets.QLabel('Smart Adjust')
        self.enable_adjust_rbtn = QtWidgets.QRadioButton('Enable')
        self.enable_adjust_rbtn.setChecked(True)
        self.smart_adjust_btn = QtWidgets.QPushButton('Run')
        self.smart_adjust_btn.setMaximumWidth(30)
        self.off_adjust_rbtn = QtWidgets.QRadioButton('Disable')
        smart_adjust_rbtn_group = QtWidgets.QButtonGroup()
        smart_adjust_rbtn_group.addButton(self.enable_adjust_rbtn)
        smart_adjust_rbtn_group.addButton(self.off_adjust_rbtn)
        smart_adjust_rbtn_group.setObjectName('smart_adjust_rbtn_group')
        smart_adjust_rbtn_group.setExclusive(True)
        smart_adjust_rbtn_group.setParent(smart_adjust_layout)

        smart_adjust_layout.addWidget(smart_label)
        smart_adjust_layout.insertStretch(1, 1)
        smart_adjust_layout.addWidget(self.enable_adjust_rbtn, 1)
        smart_adjust_layout.addWidget(self.off_adjust_rbtn, 1)
        smart_adjust_layout.addWidget(self.smart_adjust_btn)

        #  --------------------------------------------------------------------
        rerun_layout = QtWidgets.QHBoxLayout()
        self.create_embed_nodes_btn = QtWidgets.QPushButton("Create Embed Nodes")
        self.match_guides_toEmbed_btn = QtWidgets.QPushButton("Match Guides")
        rerun_layout.addWidget(self.create_embed_nodes_btn)
        rerun_layout.addWidget(self.match_guides_toEmbed_btn)

        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.run_all_settings_btn = QtWidgets.QPushButton('Run All')

        #  --------------------------------------------------------------------
        layout.addLayout(association_layout)
        layout.addWidget(self.src_geo_widget)
        layout.addLayout(h_layout_01)
        layout.addLayout(h_layout_02)
        layout.addLayout(mirror_radio_layout)
        layout.addLayout(smart_adjust_layout)
        layout.addLayout(rerun_layout)
        layout.addWidget(line)
        layout.addWidget(self.run_all_settings_btn)
        return widget

    def exportEmbedInfoWidget(self):
        widget = QtWidgets.QGroupBox('Create/Export Embed Info')
        layout = QtWidgets.QVBoxLayout()
        layout.setAlignment(QtCore.Qt.AlignTop)
        widget.setLayout(layout)

        association_list_layout = QtWidgets.QHBoxLayout()
        association_btn_layout = QtWidgets.QVBoxLayout()
        self.association_list_widget = QtWidgets.QListWidget()
        self.association_list_widget.setMaximumWidth(150)
        embed_nodes = afg_tools.DEFAULT_BIPIED_POINTS
        # embed_nodes.sort()
        self.association_list_widget.addItems(embed_nodes)

        self.enable_association_snap_btn = QtWidgets.QPushButton("Enable\nAuto Match")
        self.enable_association_btn = QtWidgets.QPushButton("Enable\nInteractive Association")
        # self.enable_association_btn.setStyleSheet("QPushButton:pressed { background-color: red }" )
        self.mirror_association_btn = QtWidgets.QPushButton("Mirror\nLeft->Right")
        self.clear_association_btn = QtWidgets.QPushButton("Clear Associations")
        self.print_association_btn = QtWidgets.QPushButton("Print\nAssociation info")
        self.enable_association_btn.setCheckable(True)

        association_btn_layout.addWidget(self.enable_association_snap_btn)
        association_btn_layout.addWidget(self.enable_association_btn)
        association_btn_layout.addWidget(self.mirror_association_btn)
        association_btn_layout.addWidget(self.clear_association_btn)
        association_btn_layout.addWidget(self.print_association_btn)
        #  -------------------------------------------------------------------
        self.export_embed_path_widget = LoadImportWidget(file_contents='Export Embed Info',
                                                         ext=['afg'],
                                                         show_import_button=False)
        self.export_association_btn = QtWidgets.QPushButton("Export Association")
        association_list_layout.addWidget(self.association_list_widget)
        association_list_layout.addLayout(association_btn_layout)
        layout.addLayout(association_list_layout)
        layout.addWidget(self.export_embed_path_widget)
        layout.addWidget(self.export_association_btn)
        self.visualizeAssociationEntry()
        return widget


class AutoFitGuideToolWidget(QtWidgets.QWidget):
    """docstring for AutoFitGuideToolWidget"""
    def __init__(self, parent=None):
        super(AutoFitGuideToolWidget, self).__init__(parent=parent)
        self.setWindowTitle("AFG Tool Widget")
        self.setContentsMargins(0, 0, 0, 0)
        self.mainLayout = QtWidgets.QVBoxLayout()
        self.mainLayout.setSpacing(0)
        self.mainLayout.setAlignment(QtCore.Qt.AlignTop)
        self.setLayout(self.mainLayout)
        self.mainLayout.addWidget(self.loadSettingsWidget())
        self.mainLayout.addWidget(self.afgTabWidget())

        self.afb_widget = AutoFitBipedWidget(parent=parent)
        self.afb_widget.model_path = self.model_path_widget
        self.afb_widget.guide_path = self.guide_path_widget
        self.relative_placement_widget = QtWidgets.QWidget()
        self.relative_placement_widget.setToolTip("Placeholder!")
        self.afg_tab_widget.addTab(self.afb_widget, 'AutoFitBipedWidget')
        self.afg_tab_widget.addTab(self.relative_placement_widget,
                                   'Relative Placement')

    def loadSettingsWidget(self):
        self.load_settings_widget = QtWidgets.QGroupBox("Load Model | Guide")
        self.load_settings_layout = QtWidgets.QVBoxLayout()
        self.load_settings_widget.setLayout(self.load_settings_layout)
        self.model_path_widget = LoadImportWidget(file_contents='Models',
                                                  import_type='maya',
                                                  ext=['ma', 'mb'])
        self.load_settings_layout.addWidget(self.model_path_widget)

        self.guide_path_widget = LoadImportWidget(file_contents='Guides',
                                                  import_type='mgear',
                                                  ext=['sgt'])
        self.load_settings_layout.addWidget(self.guide_path_widget)
        return self.load_settings_widget

    def afgTabWidget(self):
        self.afg_tab_widget = QtWidgets.QTabWidget()
        self.afg_tab_widget.setContentsMargins(0, 0, 0, 0)
        return self.afg_tab_widget


class AutoFitGuideTool(QtWidgets.QMainWindow):
    """docstring for AutoFitGuideTool"""
    def __init__(self, parent=None):
        self.afg_callback_managers = []
        super(AutoFitGuideTool, self).__init__(parent=parent)
        self.parent = parent
        self.setWindowTitle(WINDOW_TITLE)
        self.setObjectName(self.__class__.__name__)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.statusBar().showMessage("Starting up...", 3000)
        self.setCentralWidget(AutoFitGuideToolWidget(parent=self))

    def closeEvent(self, evnt):
        for manager in self.afg_callback_managers:
            print(manager)
            manager.removeAllManagedCB()
        try:
            super(AutoFitGuideTool, self).closeEvent(evnt)
        except TypeError:
            pass
