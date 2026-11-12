import copy
import json

from calibre.utils.config import JSONConfig
from qt.core import (
    QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPlainTextEdit, QPushButton, Qt, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget)

from calibre_plugins.epub_scrubber.rules import (
    PackError, export_pack, install_pack, parse_pack, validate_regex)

prefs = JSONConfig('plugins/epub_scrubber')
prefs.defaults['packs'] = []
prefs.defaults['replacements'] = []
prefs.defaults['remove_files'] = []

CHECKED = Qt.CheckState.Checked
UNCHECKED = Qt.CheckState.Unchecked


def _check_item(checked, editable=True):
    item = QTableWidgetItem()
    flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
    if editable:
        flags |= Qt.ItemFlag.ItemIsUserCheckable
    item.setFlags(flags)
    item.setCheckState(CHECKED if checked else UNCHECKED)
    return item


def _text_item(text):
    item = QTableWidgetItem(text)
    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    return item


def _button_row(*buttons):
    row = QHBoxLayout()
    for label, slot in buttons:
        button = QPushButton(label)
        button.clicked.connect(slot)
        row.addWidget(button)
    row.addStretch()
    return row


def _table(headers):
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.horizontalHeader().setStretchLastSection(True)
    table.verticalHeader().setVisible(False)
    return table


class ReplacementDialog(QDialog):

    def __init__(self, parent, rule=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle('Replacement rule')
        rule = rule or {}
        self.find = QLineEdit(rule.get('find', ''))
        self.replace = QLineEdit(rule.get('replace', ''))
        self.regex = QCheckBox('Regular expression')
        self.regex.setChecked(rule.get('regex', False))
        self.ignore_case = QCheckBox('Ignore case')
        self.ignore_case.setChecked(rule.get('ignore_case', False))
        self.error = QLabel()
        self.error.setStyleSheet('color: red')
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form = QFormLayout(self)
        form.addRow('Find:', self.find)
        form.addRow('Replace with:', self.replace)
        form.addRow(self.regex)
        form.addRow(self.ignore_case)
        form.addRow(self.error)
        form.addRow(buttons)
        self.resize(500, self.sizeHint().height())

    def accept(self):
        find = self.find.text()
        if not find:
            self.error.setText('Find must not be empty.')
            return
        if self.regex.isChecked():
            error = validate_regex(find, self.ignore_case.isChecked(), self.replace.text())
            if error:
                self.error.setText('Invalid regular expression: %s' % error)
                return
        QDialog.accept(self)

    def rule(self, enabled=True):
        return {'find': self.find.text(), 'replace': self.replace.text(),
                'regex': self.regex.isChecked(), 'ignore_case': self.ignore_case.isChecked(),
                'enabled': enabled}


class ConfigWidget(QWidget):

    def __init__(self):
        QWidget.__init__(self)
        # Edit copies; nothing is persisted until save_settings
        self.packs = copy.deepcopy(prefs['packs'])
        self.replacements = copy.deepcopy(prefs['replacements'])
        self.remove_files = copy.deepcopy(prefs['remove_files'])

        layout = QVBoxLayout(self)

        packs_box = QGroupBox('Packs')
        packs_layout = QVBoxLayout(packs_box)
        self.pack_list = QListWidget()
        packs_layout.addWidget(self.pack_list)
        packs_layout.addLayout(_button_row(
            ('Install pack…', self.install_pack),
            ('Remove', self.remove_pack),
            ('View rules', self.view_pack)))
        layout.addWidget(packs_box)

        repl_box = QGroupBox('My replacements')
        repl_layout = QVBoxLayout(repl_box)
        self.repl_table = _table(['Enabled', 'Find', 'Replace', 'Regex', 'Ignore case'])
        self.repl_table.itemDoubleClicked.connect(self.edit_replacement)
        repl_layout.addWidget(self.repl_table)
        repl_layout.addLayout(_button_row(
            ('Add', self.add_replacement),
            ('Edit', self.edit_replacement),
            ('Delete', self.delete_replacement),
            ('Move up', lambda: self.move_replacement(-1)),
            ('Move down', lambda: self.move_replacement(1))))
        layout.addWidget(repl_box)

        files_box = QGroupBox('My file removals')
        files_layout = QVBoxLayout(files_box)
        self.files_table = _table(['Enabled', 'Pattern'])
        self.files_table.itemDoubleClicked.connect(self.edit_remove_file)
        files_layout.addWidget(self.files_table)
        files_layout.addLayout(_button_row(
            ('Add', self.add_remove_file),
            ('Edit', self.edit_remove_file),
            ('Delete', self.delete_remove_file)))
        layout.addWidget(files_box)

        layout.addLayout(_button_row(('Export my rules…', self.export_rules)))

        self.refresh_packs()
        self.refresh_replacements()
        self.refresh_remove_files()

    # Checkbox state lives in the widgets; copy it back before changing the lists

    def sync(self):
        for row in range(self.pack_list.count()):
            self.packs[row]['enabled'] = self.pack_list.item(row).checkState() == CHECKED
        for row, rule in enumerate(self.replacements):
            rule['enabled'] = self.repl_table.item(row, 0).checkState() == CHECKED
        for row, rule in enumerate(self.remove_files):
            rule['enabled'] = self.files_table.item(row, 0).checkState() == CHECKED

    def save_settings(self):
        self.sync()
        prefs['packs'] = self.packs
        prefs['replacements'] = self.replacements
        prefs['remove_files'] = self.remove_files

    # Packs

    def refresh_packs(self):
        self.pack_list.clear()
        for pack in self.packs:
            label = pack['name']
            if pack.get('version'):
                label += ' ' + pack['version']
            if pack.get('description'):
                label += ' — ' + pack['description']
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(CHECKED if pack.get('enabled', True) else UNCHECKED)
            self.pack_list.addItem(item)

    def selected_pack(self):
        row = self.pack_list.currentRow()
        return row if 0 <= row < len(self.packs) else None

    def install_pack(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Install pack', '', 'Pack files (*.json)')
        if not path:
            return
        try:
            with open(path, encoding='utf-8') as f:
                pack = parse_pack(f.read())
        except (PackError, OSError, UnicodeDecodeError) as err:
            QMessageBox.warning(self, 'Could not install pack', str(err))
            return
        self.sync()
        if any(p['name'] == pack['name'] for p in self.packs):
            answer = QMessageBox.question(
                self, 'Replace pack', "Replace installed pack '%s'?" % pack['name'])
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.packs = install_pack(self.packs, pack)
        self.refresh_packs()

    def remove_pack(self):
        row = self.selected_pack()
        if row is None:
            return
        answer = QMessageBox.question(
            self, 'Remove pack', "Remove pack '%s'?" % self.packs[row]['name'])
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.sync()
        del self.packs[row]
        self.refresh_packs()

    def view_pack(self):
        row = self.selected_pack()
        if row is None:
            return
        pack = self.packs[row]
        lines = ['Replacements:']
        for rule in pack['replacements']:
            options = [o for o in ('regex', 'ignore_case') if rule.get(o)]
            lines.append('  find: %s' % rule['find'])
            lines.append('  replace with: %s%s' % (
                rule['replace'], '   [%s]' % ', '.join(options) if options else ''))
            lines.append('')
        lines.append('File removals:')
        lines.extend('  %s' % rule['pattern'] for rule in pack['remove_files'])
        dialog = QDialog(self)
        dialog.setWindowTitle(pack['name'])
        text = QPlainTextEdit('\n'.join(lines))
        text.setReadOnly(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.addWidget(text)
        dialog_layout.addWidget(buttons)
        dialog.resize(600, 400)
        dialog.exec()

    # Replacements

    def refresh_replacements(self, select=None):
        table = self.repl_table
        table.setRowCount(len(self.replacements))
        for row, rule in enumerate(self.replacements):
            table.setItem(row, 0, _check_item(rule.get('enabled', True)))
            table.setItem(row, 1, _text_item(rule['find']))
            table.setItem(row, 2, _text_item(rule['replace']))
            table.setItem(row, 3, _check_item(rule['regex'], editable=False))
            table.setItem(row, 4, _check_item(rule['ignore_case'], editable=False))
        if select is not None:
            table.selectRow(select)

    def selected_replacement(self):
        row = self.repl_table.currentRow()
        return row if 0 <= row < len(self.replacements) else None

    def add_replacement(self):
        dialog = ReplacementDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.sync()
            self.replacements.append(dialog.rule())
            self.refresh_replacements(len(self.replacements) - 1)

    def edit_replacement(self, *args):
        row = self.selected_replacement()
        if row is None:
            return
        self.sync()
        rule = self.replacements[row]
        dialog = ReplacementDialog(self, rule)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.replacements[row] = dialog.rule(rule.get('enabled', True))
            self.refresh_replacements(row)

    def delete_replacement(self):
        row = self.selected_replacement()
        if row is None:
            return
        self.sync()
        del self.replacements[row]
        self.refresh_replacements()

    def move_replacement(self, offset):
        row = self.selected_replacement()
        if row is None or not 0 <= row + offset < len(self.replacements):
            return
        self.sync()
        rules = self.replacements
        rules[row], rules[row + offset] = rules[row + offset], rules[row]
        self.refresh_replacements(row + offset)

    # File removals

    def refresh_remove_files(self, select=None):
        table = self.files_table
        table.setRowCount(len(self.remove_files))
        for row, rule in enumerate(self.remove_files):
            table.setItem(row, 0, _check_item(rule.get('enabled', True)))
            table.setItem(row, 1, _text_item(rule['pattern']))
        if select is not None:
            table.selectRow(select)

    def ask_pattern(self, current=''):
        pattern, ok = QInputDialog.getText(
            self, 'File removal', 'Pattern (e.g. **/*.info):', text=current)
        while ok and not pattern.strip():
            QMessageBox.warning(self, 'File removal', 'Pattern must not be empty.')
            pattern, ok = QInputDialog.getText(
                self, 'File removal', 'Pattern (e.g. **/*.info):', text=current)
        return pattern.strip() if ok else None

    def add_remove_file(self):
        pattern = self.ask_pattern()
        if pattern:
            self.sync()
            self.remove_files.append({'pattern': pattern, 'enabled': True})
            self.refresh_remove_files(len(self.remove_files) - 1)

    def edit_remove_file(self, *args):
        row = self.files_table.currentRow()
        if not 0 <= row < len(self.remove_files):
            return
        pattern = self.ask_pattern(self.remove_files[row]['pattern'])
        if pattern:
            self.sync()
            self.remove_files[row]['pattern'] = pattern
            self.refresh_remove_files(row)

    def delete_remove_file(self):
        row = self.files_table.currentRow()
        if not 0 <= row < len(self.remove_files):
            return
        self.sync()
        del self.remove_files[row]
        self.refresh_remove_files()

    # Export

    def export_rules(self):
        name, ok = QInputDialog.getText(self, 'Export my rules', 'Pack name:')
        name = name.strip()
        if not ok or not name:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, 'Export my rules', name + '.json', 'Pack files (*.json)')
        if not path:
            return
        self.sync()
        pack = export_pack(name, self.replacements, self.remove_files)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(json.dumps(pack, indent=2) + '\n')
        except OSError as err:
            QMessageBox.warning(self, 'Could not export rules', str(err))
