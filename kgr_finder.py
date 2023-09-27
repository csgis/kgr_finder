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
from qgis.PyQt.QtWidgets import QDialog
from qgis.utils import iface

from .options import ConfigOptionsPage, KgrFinderOptionsFactory
from .resources import *
from .tools import FindKGRData, PolygonLayerDialog
from qgis.PyQt.QtWidgets import QAction

class KgrFinder:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        # save reference to the QGIS interface
        self.iface = iface
        self.tool = None

    def initGui(self):
        config_options_page = ConfigOptionsPage(None)

        if not hasattr(self, 'find_data_by_drawn_polygon'):
            # create action that will start plugin configuration
            self.find_data_by_drawn_polygon = QAction(QIcon(":/plugins/kgr_finder/greif_polygon.png"),
                                "Find data by drawing a polygon",
                                self.iface.mainWindow())
                
            self.find_data_by_drawn_polygon.setObjectName("KGRAction")
            self.find_data_by_drawn_polygon.setCheckable(True)
            self.find_data_by_drawn_polygon.toggled.connect(self.togglePolygonDrawingTool)

            # add toolbar button and menu item
            self.iface.addToolBarIcon(self.find_data_by_drawn_polygon)
            self.iface.addPluginToMenu("&KGR plugins", self.find_data_by_drawn_polygon)


        if not hasattr(self, 'find_data_by_layer_tool'):
            # Add a new action for opening the dialog
            self.find_data_by_layer_tool = QAction(QIcon(":/plugins/kgr_finder/greif_rectangle.png"),
                                    "Find data by polygon layer bounds",
                                    self.iface.mainWindow())
            self.find_data_by_layer_tool.setObjectName("DialogAction")
            self.find_data_by_layer_tool.setCheckable(True)
            self.find_data_by_layer_tool.toggled.connect(self.toggleLayerTool)

             # add toolbar button and menu item
            self.iface.addPluginToMenu("&KGR plugins", self.find_data_by_layer_tool)
            self.iface.addToolBarIcon(self.find_data_by_layer_tool)


        self.options_factory = KgrFinderOptionsFactory()
        self.options_factory.setTitle('KGR Finder')
        iface.registerOptionsWidgetFactory(self.options_factory)


    def openKGRLayerQueryDialog(self):
        self.iface.mapCanvas().unsetMapTool(self.tool)
        print("toggle")
        dialog = PolygonLayerDialog()
        result = dialog.exec_()

        if result == QDialog.Accepted:
            selected_layer_name = dialog.layer_combo.currentText()
            print("done")
            if selected_layer_name != 'Select a layer':
                selected_layer = QgsProject.instance().mapLayersByName(selected_layer_name)[0]
                self.tool = FindKGRData(self.iface.mapCanvas()) 
                self.tool.setSelectedLayer(selected_layer)

                self.tool.processPolygonCoordinates()



    def unload(self):
        # remove the plugin menu item and icon
        self.iface.removePluginMenu("&KGR plugins", self.find_data_by_drawn_polygon)
        self.iface.removeToolBarIcon(self.find_data_by_drawn_polygon)
        self.iface.removePluginMenu("&KGR plugins", self.find_data_by_layer_tool)
        iface.unregisterOptionsWidgetFactory(self.options_factory)

        QgsSettings().remove("/KgrFinder/settings_tags")
        QgsSettings().remove("/KgrFinder/osm_tags")

        # Remove the new tool
        self.iface.mapCanvas().unsetMapTool(self.tool)
        self.tool = None

    def togglePolygonDrawingTool(self, checked):
        if checked:
            self.find_data_by_layer_tool.setChecked(False)  # Uncheck the other button
            self.iface.mapCanvas().unsetMapTool(self.tool)
            self.tool = FindKGRData(self.iface.mapCanvas())
            self.iface.mapCanvas().setMapTool(self.tool)
            self.tool = self.tool
        else:
            self.iface.mapCanvas().unsetMapTool(self.tool)
            self.tool = None

    def toggleLayerTool(self, checked):
        if checked:
            self.find_data_by_drawn_polygon.setChecked(False)  # Uncheck the other button
            self.iface.mapCanvas().unsetMapTool(self.tool)
            self.tool = None  # Reset the tool to None
            self.openKGRLayerQueryDialog()  # Call the dialog function

        else:
            self.iface.mapCanvas().unsetMapTool(self.tool)
            self.tool = None

    def run(self):
        # create and show a configuration dialog or something similar
        print("KGR Plugin: run called!")


