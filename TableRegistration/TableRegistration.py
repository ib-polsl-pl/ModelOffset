import json
import os
import unittest
import logging
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
import numpy as np

#
# TableRegistration
#

class TableRegistration(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Additional register of the table"  # Pro tip: the name should begin with "A"
    self.parent.categories = ["IGT"]  
    self.parent.dependencies = []  # TODO: add here list of module names that this module requires
    self.parent.contributors = ["Bartłomiej Pyciński (Silesian Univ Tech, Poland)"]  
    self.parent.helpText = """
A module to register model with additionally collected points.
See more information in <a href="https://github.com/ib-polsl-pl/IB_nawigacja.git">module documentation</a>.
"""
    # TODO: replace with organization, grant and thanks
    self.parent.acknowledgementText = """TBD.
"""

    # Additional initialization step after application startup is complete
    pass


#
# TableRegistrationWidget
#

class TableRegistrationWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent=None):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.__init__(self, parent)
    VTKObservationMixin.__init__(self)  # needed for parameter node observation
    self.logic = None
    self._parameterNode = None
    self._updatingGUIFromParameterNode = False

  def setup(self):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.setup(self)

    # Load widget from .ui file (created by Qt Designer).
    # Additional widgets can be instantiated manually and added to self.layout.
    uiWidget = slicer.util.loadUI(self.resourcePath('UI/TableRegistration.ui'))
    self.layout.addWidget(uiWidget)
    self.ui = slicer.util.childWidgetVariables(uiWidget)

    # Set scene in MRML widgets. Make sure that in Qt designer the top-level qMRMLWidget's
    # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
    # "setMRMLScene(vtkMRMLScene*)" slot.
    uiWidget.setMRMLScene(slicer.mrmlScene)

    # Create logic class. Logic implements all computations that should be possible to run
    # in batch mode, without a graphical user interface.
    self.logic = TableRegistrationLogic()

    # Connections

    # These connections ensure that we update parameter node when scene is closed
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

    # These connections ensure that whenever user changes some settings on the GUI, that is saved in the MRML scene
    # (in the selected parameter node).
    # BPWARNING add line here if a new widget is added
    self.ui.patientVolumeSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
    self.ui.tablePointsSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
    self.ui.fromPatientPointsSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
    self.ui.toPatientPointsSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
    self.ui.finalTransformSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
    self.ui.offsetXCheckBox.connect("toggled(bool)", self.updateParameterNodeFromGUI)
    self.ui.offsetYCheckBox.connect("toggled(bool)", self.updateParameterNodeFromGUI)
    self.ui.offsetZCheckBox.connect("toggled(bool)", self.updateParameterNodeFromGUI)

    # Buttons
    self.ui.applyRotateButton.connect('clicked(bool)', self.onApplyRotationButton)
    self.ui.applyTranslateButton.connect('clicked(bool)', self.onApplyTranslationButton)

    # Make sure parameter node is initialized (needed for module reload)
    self.initializeParameterNode()

  def cleanup(self):
    """
    Called when the application closes and the module widget is destroyed.
    """
    self.removeObservers()

  def enter(self):
    """
    Called each time the user opens this module.
    """
    # Make sure parameter node exists and observed
    self.initializeParameterNode()

  def exit(self):
    """
    Called each time the user opens a different module.
    """
    # Do not react to parameter node changes (GUI wlil be updated when the user enters into the module)
    self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)

  def onSceneStartClose(self, caller, event):
    """
    Called just before the scene is closed.
    """
    # Parameter node will be reset, do not use it anymore
    self.setParameterNode(None)

  def onSceneEndClose(self, caller, event):
    """
    Called just after the scene is closed.
    """
    # If this module is shown while the scene is closed then recreate a new parameter node immediately
    if self.parent.isEntered:
      self.initializeParameterNode()

  def initializeParameterNode(self):
    """
    Ensure parameter node exists and observed.
    """
    # Parameter node stores all user choices in parameter values, node selections, etc.
    # so that when the scene is saved and reloaded, these settings are restored.

    self.setParameterNode(self.logic.getParameterNode())

    # Select default input nodes if nothing is selected yet to save a few clicks for the user
    pass


  def setParameterNode(self, inputParameterNode):
    """
    Set and observe parameter node.
    Observation is needed because when the parameter node is changed then the GUI must be updated immediately.
    """

    if inputParameterNode:
      self.logic.setDefaultParameters(inputParameterNode)

    # Unobserve previously selected parameter node and add an observer to the newly selected.
    # Changes of parameter node are observed so that whenever parameters are changed by a script or any other module
    # those are reflected immediately in the GUI.
    if self._parameterNode is not None:
      self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)
    self._parameterNode = inputParameterNode
    if self._parameterNode is not None:
      self.addObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)

    # Initial GUI update
    self.updateGUIFromParameterNode()

  def updateGUIFromParameterNode(self, caller=None, event=None):
    """
    This method is called whenever parameter node is changed.
    The module GUI is updated to show the current state of the parameter node.
    """

    if self._parameterNode is None or self._updatingGUIFromParameterNode:
      return

    # Make sure GUI changes do not call updateParameterNodeFromGUI (it could cause infinite loop)
    self._updatingGUIFromParameterNode = True

    # Update node selectors and sliders
    # BPWARNING add line here if a new widget is added
    self.ui.patientVolumeSelector.setCurrentNode(self._parameterNode.GetNodeReference("patientVolume"))
    self.ui.tablePointsSelector.setCurrentNode(self._parameterNode.GetNodeReference("tablePoints"))
    self.ui.fromPatientPointsSelector.setCurrentNode(self._parameterNode.GetNodeReference("fromPatientPoints"))
    self.ui.toPatientPointsSelector.setCurrentNode(self._parameterNode.GetNodeReference("toPatientPoints"))
    self.ui.finalTransformSelector.setCurrentNode(self._parameterNode.GetNodeReference("finalTransform"))
    self.ui.offsetXCheckBox.checked = (self._parameterNode.GetParameter("ApplyOffsetX") == "true")
    self.ui.offsetYCheckBox.checked = (self._parameterNode.GetParameter("ApplyOffsetY") == "true")
    self.ui.offsetZCheckBox.checked = (self._parameterNode.GetParameter("ApplyOffsetZ") == "true")

    # Update buttons states and tooltips
    if self._parameterNode.GetNodeReference("patientVolume") \
            and self._parameterNode.GetNodeReference("tablePoints")\
            and self._parameterNode.GetNodeReference("finalTransform"):
      self.ui.applyRotateButton.enabled = True
    else:
      self.ui.applyRotateButton.enabled = False

    if self._parameterNode.GetNodeReference("patientVolume") \
            and self._parameterNode.GetNodeReference("fromPatientPoints") \
            and self._parameterNode.GetNodeReference("toPatientPoints") \
            and self._parameterNode.GetNodeReference("finalTransform"):
      self.ui.applyTranslateButton.enabled = True
    else:
      self.ui.applyTranslateButton.enabled = False

    # All the GUI updates are done
    self._updatingGUIFromParameterNode = False

  def updateParameterNodeFromGUI(self, caller=None, event=None):
    """
    This method is called when the user makes any change in the GUI.
    The changes are saved into the parameter node (so that they are restored when the scene is saved and loaded).
    """

    if self._parameterNode is None or self._updatingGUIFromParameterNode:
      return

    wasModified = self._parameterNode.StartModify()  # Modify all properties in a single batch

    # BPWARNING add line here if a new widget is added
    self._parameterNode.SetNodeReferenceID("patientVolume", self.ui.patientVolumeSelector.currentNodeID)
    self._parameterNode.SetNodeReferenceID("tablePoints", self.ui.tablePointsSelector.currentNodeID)
    self._parameterNode.SetNodeReferenceID("fromPatientPoints", self.ui.fromPatientPointsSelector.currentNodeID)
    self._parameterNode.SetNodeReferenceID("toPatientPoints", self.ui.toPatientPointsSelector.currentNodeID)
    self._parameterNode.SetNodeReferenceID("finalTransform", self.ui.finalTransformSelector.currentNodeID)
    self._parameterNode.SetParameter("ApplyOffsetX", "true" if self.ui.offsetXCheckBox.checked else "false")
    self._parameterNode.SetParameter("ApplyOffsetY", "true" if self.ui.offsetYCheckBox.checked else "false")
    self._parameterNode.SetParameter("ApplyOffsetZ", "true" if self.ui.offsetZCheckBox.checked else "false")

    self._parameterNode.EndModify(wasModified)

  def onApplyTranslationButton(self):
    try:
      self.logic.process_translate(self.ui.patientVolumeSelector.currentNode(),
        self.ui.fromPatientPointsSelector.currentNode(),
        self.ui.toPatientPointsSelector.currentNode(),
        self.ui.finalTransformSelector.currentNode())
    except Exception as e:
      slicer.util.errorDisplay("Failed to compute results: "+str(e))
      import traceback
      traceback.print_exc()


  def onApplyRotationButton(self):
    """
    Run processing when user clicks "Apply" button.
    """
    try:
      self.logic.process_rotate(self.ui.patientVolumeSelector.currentNode(),
        self.ui.tablePointsSelector.currentNode(),
        self.ui.finalTransformSelector.currentNode())
    except Exception as e:
      slicer.util.errorDisplay("Failed to compute results: "+str(e))
      import traceback
      traceback.print_exc()


#
# TableRegistrationLogic
#

class TableRegistrationLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self):
    """
    Called when the logic class is instantiated. Can be used for initializing member variables.
    """
    ScriptedLoadableModuleLogic.__init__(self)
    self.shNode = slicer.mrmlScene.GetSubjectHierarchyNode()

  def setDefaultParameters(self, parameterNode):
    """
    Initialize parameter node with default settings.
    """
    if not parameterNode.GetParameter("Threshold"):
      parameterNode.SetParameter("Threshold", "100.0")
    if not parameterNode.GetParameter("Invert"):
      parameterNode.SetParameter("Invert", "false")

  def process(self):
    pass

  def process_rotate(self, patientVolume, tablePoints, finalTransform):
    """
    Run the processing algorithm.
    Can be used without GUI widget.
    :param patientVolume: Input volume
    :param tablePoints: sequence of the points
    """

    if not patientVolume or not tablePoints or not finalTransform:
      raise ValueError("Input data are invalid")

    #print( patientVolume, tablePoints, finalTransform)

    c0 = np.array([np.nan, np.nan, np.nan])
    c1 = np.array([np.nan, np.nan, np.nan])
    c2 = np.array([np.nan, np.nan, np.nan])

    tablePoints.GetNthControlPointPositionWorld(0, c0)
    tablePoints.GetNthControlPointPositionWorld(1, c1)
    tablePoints.GetNthControlPointPositionWorld(2, c2)

    rl = c1-c0
    vtk.vtkMath.Normalize(rl)
    si = c2-c1
    vtk.vtkMath.Normalize(si)
    ap = np.array([np.nan, np.nan, np.nan])
    vtk.vtkMath.Cross(rl, si, ap)
    angle_rl_si = abs(vtk.vtkMath.DegreesFromRadians(vtk.vtkMath.AngleBetweenVectors(rl, si)))
    if not (85 < angle_rl_si < 95):
      logging.warning("Control points on the table are collected very poorly. Got %f" % (angle_rl_si,))

    rotation = np.zeros((4,4))
    rotation[-1, -1] = 1
    vtk.vtkMath.Orthogonalize3x3([rl, si, ap], rotation[:3, :3])

    if finalTransform.GetParentTransformNode():
      raise RuntimeError("Not implemented yet. Currently, final transformation should not be attached to any other transform.")

    t = finalTransform.GetTransformToParent()
    t.SetMatrix(rotation.ravel())

    # this should be done outside the plugin:
    # tablePoints.SetAndObserveTransformNodeID(finalTransform.GetID())

  def process_translate(self, patientVolume, fromPatientPoints, toPatientPoints, finalTransform):
    print(patientVolume, fromPatientPoints, toPatientPoints, finalTransform)
    if not patientVolume or not fromPatientPoints or not toPatientPoints or not finalTransform:
      raise ValueError("Input data is empty")



#
# TableRegistrationTest
#
class TableRegistrationTest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  Prevoiusy used ScriptedLoadableModuleTest base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py

  Now it was cleaned
  """

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    pass

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_TableRegistration1()

  def test_TableRegistration1(self):
    self.delayDisplay("Starting the test")
    self.delayDisplay('Test passed')
