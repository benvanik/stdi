# Copyright 2012 Google Inc. All Rights Reserved.

__author__ = 'benvanik@google.com (Ben Vanik)'


import sublime
import sublime_plugin


_view_mappings = {}


def _add_custom_view(view, custom_view):
  global _view_mappings
  _view_mappings[view.id()] = custom_view


def _remove_custom_view(view):
  global _view_mappings
  if view.id() in _view_mappings:
    del _view_mappings[view.id()]


def cleanup_all():
  global _view_mappings
  #for custom_view in _view_mappings.values():
  #  custom_view.close()


def get_custom_view(view):
  global _view_mappings
  return _view_mappings.get(view.id(), None)


class CustomView(object):
  """A ST view that is used for debugger IO.
  """
  def __init__(self, window, debugger, title, *args, **kwargs):
    """Initializes a custom view.

    Args:
      window: Target sublime window.
      debugger: Debugger.
      title: View title.
    """
    self._window = window
    self._debugger = debugger
    active_view = window.active_view()
    self._view = window.new_file()
    window.focus_view(active_view)
    self._view.set_name(title)
    self._view.set_read_only(True)
    self._view.set_scratch(True)
    #self._view.set_syntax_file('Packages/Python/Python.tmLanguage')
    settings = self._view.settings()
    settings.set('stdi_callstack', True)
    settings.set('command_mode', False)
    settings.set('line_numbers', False)
    settings.set('caret_style', 'blink')
    settings.set('auto_complete', False)
    settings.set('draw_white_space', 'none')
    settings.set('word_wrap', False)
    settings.set('gutter', True)
    settings.set('spell_check', False)
    settings.set('rulers', [])
    #settings.set('color_scheme', os.path.join(PACKAGE_DIR, 'stdi.tmTheme'))
    _add_custom_view(self._view, self)

  def window(self):
    return self._window

  def debugger(self):
    return self._debugger

  def view(self):
    return self._view

  def focus(self):
    self._window.focus_view(self._view)

  def clear(self):
    view = self.view()
    view.set_read_only(False)
    edit = view.begin_edit()
    view.erase(edit, sublime.Region(0, view.size()))
    view.end_edit(edit)
    view.set_read_only(True)
    view.sel().clear()

  def close(self):
    active_view = self._window.active_view()
    self._window.focus_view(self._view)
    self._window.run_command('close')
    self._window.focus_view(active_view)
    _remove_custom_view(self._view)

  def on_selection_modified(self):
    pass


class TreeView(CustomView):
  """A ST view displaying a navigable.
  """
  def __init__(self, window, debugger, title, *args, **kwargs):
    """Initializes a tree view.

    Args:
      window: Target sublime window.
      debugger: Debugger.
      title: View title.
    """
    super(TreeView, self).__init__(window, debugger, title, *args, **kwargs)
    self._root_node = None

  def root_node(self):
    return self._root_node

  def clear(self):
    self._root_node = None
    super(TreeView, self).clear()

  def reset(self, root_node):
    self.view().sel().clear()
    self._root_node = root_node
    view = self.view()
    view.set_read_only(False)
    edit = view.begin_edit()
    view.erase(edit, sublime.Region(0, view.size()))
    if self._root_node:
      self._root_node._insert_into_view(edit, 0)
    view.end_edit(edit)
    view.set_read_only(True)

  def on_selection_modified(self):
    if not self._root_node:
      return
    point = 0
    for region in self.view().sel():
      point = region.begin()
      break
    if point == 0:
      return
    self.view().sel().clear()
    self._root_node.on_click(point)


class TreeNode(object):
  """An individual node in a tree view.
  """
  _next_key_id = 0

  def __init__(self, view, *args, **kwargs):
    """Initializers a tree node.

    Args:
      view: View the tree is in.
    """
    self._view = view
    self._region_key = str(TreeNode._next_key_id)
    TreeNode._next_key_id += 1
    self._is_expanded = False
    self._is_expanding = False
    self._child_nodes = None
    self._tree_level = 0

  def view(self):
    return self._view

  def label(self):
    return ''

  def description(self):
    return None

  def has_children(self):
    return False

  def query_children(self, callback):
    pass

  def can_collapse(self):
    return True

  def is_expanded(self):
    return self._is_expanded

  def set_expanded(self, value):
    view = self.view()
    if self._is_expanded == value:
      return
    if not self.can_collapse() and not value:
      return
    self._is_expanded = value
    if not self._is_expanded:
      if self._child_nodes:
        view.set_read_only(False)
        edit = view.begin_edit()
        for node in self._child_nodes:
          node._remove_from_view(edit)
        view.end_edit(edit)
        view.set_read_only(True)
    else:
      if self._is_expanding:
        return
      if not self.has_children():
        return
      self._is_expanding = True
      def _on_query_children(child_nodes):
        self._is_expanding = False
        if not self._is_expanded:
          return
        self._child_nodes = child_nodes
        regions = view.get_regions(self._region_key)
        end_point = regions[0].end() if len(regions) else 0
        view.set_read_only(False)
        edit = view.begin_edit()
        for node in self._child_nodes:
          node._set_tree_level(self._tree_level + 1)
          end_point = node._insert_into_view(edit, end_point)
        view.end_edit(edit)
        view.set_read_only(True)
      if self._child_nodes:
        _on_query_children(self._child_nodes)
      else:
        self.query_children(_on_query_children)

  def tree_level(self):
    return self._tree_level

  def _set_tree_level(self, value):
    self._tree_level = value

  def _insert_into_view(self, edit, point):
    indent = ''
    for n in range(self._tree_level):
      indent += '  '
    node_value = self.label()
    description = self.description()
    if description:
      node_value = '%s: %s' % (node_value, description)
    node_text = '%s%s\n' % (indent, node_value)
    end_point = point + self._view.insert(edit, point, node_text)
    region = sublime.Region(point, end_point)
    scope = ''
    icon = 'dot' if self.has_children() else ''
    self._view.add_regions(self._region_key, [region], scope, icon,
                           sublime.HIDDEN)
    if self._child_nodes:
      for node in self._child_nodes:
        end_point = node._insert_into_view(edit, end_point)
    return end_point

  def _remove_from_view(self, edit):
    if self._child_nodes:
      for node in self._child_nodes:
        node._remove_from_view(edit)
    regions = self._view.get_regions(self._region_key)
    for region in regions:
      self._view.erase(edit, region)
    self._view.erase_regions(self._region_key)

  def on_click(self, point):
    # Test node
    regions = self._view.get_regions(self._region_key)
    for region in regions:
      if region.contains(point):
        self.set_expanded(not self.is_expanded())
    # Test children
    # TODO(benvanik): child region range for fast detection/etc
    if self._child_nodes:
      for node in self._child_nodes:
        node.on_click(point)

