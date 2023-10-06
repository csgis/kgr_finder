# -*- coding: utf-8 -*-
"""
/***************************************************************************
  KgrFinder
  A QGIS plugin for detecting cultura places
 -------------------
  begin                : 2023-09-11
  copyright            : (C) 2023 by cuprit gbr
  email                : toni.schoenbuchner@cuprit.net
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from qgis.core import QgsProject, QgsSettings
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QDialog
from qgis.utils import iface

from .options import ConfigOptionsPage, KgrFinderOptionsFactory
from .resources import *
from .tools import DrawPolygonTool, FindKGRDataBaseTool, PolygonLayerDialog

from .utils.logger import Logger

Log = Logger()


class KgrFinder:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        self.iface = iface
        self.tool = None
        self.toolbar = self.iface.addToolBar("KGRFinder")

    def initGui(self):
        # need to initally set options
        ConfigOptionsPage(None)

        if not hasattr(self, "find_data_by_drawn_polygon"):
            self.find_data_by_drawn_polygon = QAction(
                QIcon(":/plugins/kgr_finder/assets/greif_polygon.png"),
                "Find data by drawing a polygon",
                self.iface.mainWindow(),
            )
            self.find_data_by_drawn_polygon.setObjectName("KGRAction")
            self.find_data_by_drawn_polygon.setCheckable(True)
            self.find_data_by_drawn_polygon.toggled.connect(
                self.togglePolygonDrawingTool
            )
            # self.iface.addToolBarIcon(self.find_data_by_drawn_polygon)
            self.toolbar.addAction(self.find_data_by_drawn_polygon)

            self.iface.addPluginToMenu("&KGR plugins", self.find_data_by_drawn_polygon)

        if not hasattr(self, "find_data_by_layer_tool"):
            self.find_data_by_layer_tool = QAction(
                QIcon(":/plugins/kgr_finder/assets/greif_rectangle.png"),
                "Find data by polygon layer bounds",
                self.iface.mainWindow(),
            )
            self.find_data_by_layer_tool.setObjectName("DialogAction")
            self.find_data_by_layer_tool.setCheckable(True)
            self.find_data_by_layer_tool.toggled.connect(self.toggleLayerTool)
            self.iface.addPluginToMenu("&KGR plugins", self.find_data_by_layer_tool)
            # self.iface.addToolBarIcon(self.find_data_by_layer_tool)
            self.toolbar.addAction(self.find_data_by_layer_tool)

        self.options_factory = KgrFinderOptionsFactory()
        self.options_factory.setTitle("KGR Finder")
        iface.registerOptionsWidgetFactory(self.options_factory)

    def openKGRLayerQueryDialog(self):
        self.iface.mapCanvas().unsetMapTool(self.tool)
        dialog = PolygonLayerDialog()
        result = dialog.exec_()

        if result == QDialog.Accepted:
            selected_layer_name = dialog.layer_combo.currentText()
            if selected_layer_name != "Select a layer":
                selected_layer = QgsProject.instance().mapLayersByName(
                    selected_layer_name
                )[0]
                self.tool = FindKGRDataBaseTool(self.iface.mapCanvas())
                self.tool.setSelectedLayer(selected_layer)
                self.tool.processPolygonCoordinates()

    def togglePolygonDrawingTool(self, checked):
        if checked:
            self.find_data_by_layer_tool.setChecked(False)
            self.iface.mapCanvas().unsetMapTool(self.tool)
            self.tool = DrawPolygonTool(self.iface.mapCanvas())
            self.iface.mapCanvas().setMapTool(self.tool)
        else:
            self.iface.mapCanvas().unsetMapTool(self.tool)
            self.tool = None

    def toggleLayerTool(self, checked):
        if checked:
            self.find_data_by_drawn_polygon.setChecked(False)
            self.iface.mapCanvas().unsetMapTool(self.tool)
            self.tool = None
            self.openKGRLayerQueryDialog()

        else:
            self.iface.mapCanvas().unsetMapTool(self.tool)
            self.tool = None

    def unload(self):
        self.iface.removePluginMenu("&KGR plugins", self.find_data_by_drawn_polygon)
        self.iface.removePluginMenu("&KGR plugins", self.find_data_by_layer_tool)

        self.iface.removeToolBarIcon(self.find_data_by_drawn_polygon)
        iface.unregisterOptionsWidgetFactory(self.options_factory)

        settings = QgsSettings()
        keys = settings.allKeys()
        for key in keys:
            value = settings.value(key)
            if "KgrFinder" in key:
                Log.log_debug(f"{key}: {value}")
                QgsSettings().remove(f"/{key}")

        self.iface.mapCanvas().unsetMapTool(self.tool)
        self.tool = None
        del self.toolbar

    def run(self):
        Log.log_debug("run called")
