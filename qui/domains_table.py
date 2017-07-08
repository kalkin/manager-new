#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
''' This is the graphical equivalent of `qvm-ls(1)` based on `Gtk.TreeView`'''

from __future__ import print_function

import signal

import qubesadmin
import qubesadmin.tools.qvm_ls as qvm_ls

import gi  # isort:skip
gi.require_version('Gtk', '3.0')  # isort:skip
from gi.repository import Gio, Gtk  # isort:skip pylint: disable=C0413

# pylint:disable=missing-docstring

ICON_STATE_MAP = {
    'media-playback-start': "Running",
    'system-run': "Transient",
    'media-playback-stop': "Halted"
}


def state_icon_name(vm):
    return {v: k for k, v in ICON_STATE_MAP.items()}[vm.get_power_state()]


def netvm_label(vm):
    if vm.netvm is None:
        return "process-stop"
    else:
        return vm.netvm.label.icon


def create_icon(name):
    icon_dev = Gtk.IconTheme.get_default().load_icon(name, 16, 0)
    return Gtk.Image.new_from_pixbuf(icon_dev)


class DomainsListStore(Gtk.ListStore):
    def __init__(self, app, columns, **kwargs):
        params = [
            str,
        ] * len(columns)

        super().__init__(*params, **kwargs)
        for vm in app.domains:
            if vm.name == 'dom0':
                continue
            self.append([col.cell(vm) for col in columns])


class ListBoxWindow(Gtk.Window):
    def __init__(self, app, col_names):
        super().__init__(title="Domain List")

        self.app = app
        self.filter = {'state': ["Halted"], 'vm_type': []}
        self.col_names = col_names
        self.add_bindings()
        hbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        hbox.add(self._button_bar())
        hbox.pack_start(self._tree_view(), True, True, 5)
        self.add(hbox)
        self.show_all()

    def add_bindings(self):
        self.accel_group = Gtk.AccelGroup()
        self.add_accel_group(self.accel_group)

    def _button_bar(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        buttons_data = [
            ('Running', "F2", "media-playback-start",
             self._toggle_filter_state),
            ('Transient', "F3", "system-run", self._toggle_filter_state),
            ('Halted', "F4", "media-playback-stop", self._toggle_filter_state),
            ('AppVM', "F5", None, self._toggle_filter_type),
            ('StandaloneVM', "F6", None, self._toggle_filter_type),
            ('TemplateVM', "F7", None, self._toggle_filter_type),
            ('DispVM', "F8", None, self._toggle_filter_type),
        ]

        for button_name, key, icon_name, func in buttons_data:
            key_id = Gtk.accelerator_parse(key).accelerator_key
            button = Gtk.ToggleButton("%s (%s)" % (button_name, key))
            if icon_name:
                icon = create_icon(icon_name)
                button.set_image(icon)
            if button_name not in self.filter['state'] and button_name not in self.filter['vm_type']:
                button.set_active(True)
            button.connect('toggled', func, button_name)

            button.add_accelerator("activate", self.accel_group, key_id, 0, 0)
            vbox.add(button)
        vbox.set_halign(Gtk.Align.CENTER)
        return vbox

    def _toggle_filter_state(self, widget, state):
        if widget.get_active():
            self.filter['state'].remove(state)
        else:
            self.filter['state'].append(state)

        self.filter_store.refilter()
        self.show_all()

    def _toggle_filter_type(self, widget, vm_type):
        if widget.get_active():
            self.filter['vm_type'].remove(vm_type)
        else:
            self.filter['vm_type'].append(vm_type)

        self.filter_store.refilter()
        self.show_all()

    def _tree_view(self):
        columns = []
        for col in self.col_names:
            col = col.strip().upper()
            if col in qvm_ls.Column.columns:
                columns += [qvm_ls.Column.columns[col]]

        self.set_border_width(10)

        # self.grid = Gtk.Grid()
        # self.grid.set_column_homogeneous(True)
        store = DomainsListStore(self.app, columns)
        self.filter_store = store.filter_new()
        self.filter_store.set_visible_func(self._filter_func)
        treeview = Gtk.TreeView.new_with_model(self.filter_store)
        treeview.set_search_column(2)
        for index in range(0, len(columns)):
            col = columns[index]
            if col.ls_head in ['STATE', 'LABEL', 'NETVM_LABEL']:
                title = str(" ")
                renderer = Gtk.CellRendererPixbuf()
                kwargs = {'icon-name': index}
            else:
                title = str(col.ls_head)
                renderer = Gtk.CellRendererText()
                kwargs = {'text': index}

            view_column = Gtk.TreeViewColumn(title, renderer, **kwargs)
            treeview.append_column(view_column)
        return treeview

    def _filter_func(self, model, iterator, _):
        icon_name = model[iterator][0]
        vm_type = model[iterator][3]
        state = ICON_STATE_MAP[icon_name]
        if state in self.filter['state'] or vm_type in self.filter['vm_type']:
            return False
        return True

    def reload(self):
        print("drin")


qvm_ls.Column('LABEL', attr=(lambda vm: vm.label.icon), doc="Label icon")
qvm_ls.Column('STATE', attr=state_icon_name, doc="Label icon")
qvm_ls.Column('NETVM_LABEL', attr=netvm_label, doc="Label icon")

#: Available formats. Feel free to plug your own one.
formats = {
    'simple': ('state', 'label', 'name', 'class', 'template', 'netvm_label',
               'netvm'),
    'network': ('state', 'label', 'name', 'netvm_label', 'netvm', 'ip',
                'ipback', 'gateway'),
    'full': ('state', 'label', 'name', 'class', 'qid', 'xid', 'uuid'),
    #  'perf': ('name', 'state', 'cpu', 'memory'),
    'disk': ('state', 'label', 'name', 'disk', 'priv-curr', 'priv-max',
             'priv-used', 'root-curr', 'root-max', 'root-used'),
}


def main(args=None):  # pylint:disable=unused-argument
    parser = qvm_ls.get_parser()
    try:
        args = parser.parse_args()
    except qubesadmin.exc.QubesException as e:
        parser.print_error(str(e))
        return 1

    if args.fields:
        columns = [col.strip() for col in args.fields.split(',')]
    else:
        columns = formats[args.format]

    # assume unknown columns are VM properties
    for col in columns:
        if col.upper() not in qvm_ls.Column.columns:
            qvm_ls.PropertyColumn(col.lower())

    window = ListBoxWindow(args.app, columns)
    window.connect("delete-event", Gtk.main_quit)
    w_file = Gio.File.new_for_path("/var/lib/qubes/qubes.xml")
    monitor = w_file.monitor_file(Gio.FileMonitorFlags.NONE, None)
    monitor.connect("changed", window.reload)
    window.show_all()
    Gtk.main()


if __name__ == '__main__':
    # next line is for behaving well with Ctrl+C
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    main()
