import csv
import datetime
import json
import os
import shutil
import sqlite3
import sys

import PyQt5
import vlc
from PyQt5 import Qt
from PyQt5 import QtCore
from PyQt5.QtWidgets import QMainWindow, QApplication, QFileDialog, QPushButton, QMessageBox, QTableWidget, \
    QTableWidgetItem, QLineEdit, QLabel

from music import Ui_MainWindow


class Example(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setWindowTitle('Плеер')
        self.con = sqlite3.connect('tracks_list.sqlite')
        self.cur = self.con.cursor()
        self.track_format = 'mp3'
        self.time_value.sliderReleased.connect(self.released)
        self.format.currentTextChanged.connect(self.format_changed)
        self.open_playlist_btn.clicked.connect(self.open_playlist)
        self.playlist_name = 'tracks'
        self.search_btn.clicked.connect(self.search_tracks)
        self.listWidget.itemDoubleClicked.connect(self.new_item_choosed)
        self.pause_btn.clicked.connect(self.pause)
        self.past_btn.clicked.connect(self.past)
        self.next_btn.clicked.connect(self.next)
        self.favoutit_btn.clicked.connect(self.favour_play)
        self.create_playlist_btn.clicked.connect(self.create_playlist)
        self.star.clicked.connect(self.favour)
        self.buttonGroup.buttonClicked.connect(self.volume_changed)
        self.fontComboBox.currentFontChanged.connect(self.new_font)
        self.time_value.sliderPressed.connect(self.new_time)
        self.sort_btn.clicked.connect(self.dialog)
        self.icons = ['⏸', '▶']
        self.search_edit.textEdited.connect(self.search_by_name)
        self.volume = 50
        self.export_btn.clicked.connect(self.export)
        self.design = False
        self.design_button.clicked.connect(self.start_or_finish_design)
        try:
            for name in self.cur.execute("""SELECT name FROM tracks"""):
                self.listWidget.addItem(str(name[0]))  # Если у пользователя есть треки, они отраэаются.
        except:
            self.listWidget.addItem('Треков пока нет, давайте искать!')

    def search_tracks(self):
        try:
            tmp = self.cur.execute("""SELECT name FROM playlists""").fetchall()
            for i in range(len(tmp)):  # данные из таблиц пробуют удалиться
                self.cur.execute('DROP TABLE ' + tmp[i][0])
            self.cur.execute('DELETE from favourit')
            self.cur.execute('DELETE FROM playlists')
            self.label_4.setText('Поиск..')
            self.cur.execute('DELETE from tracks')
            self.con.commit()
        except sqlite3.OperationalError:  # если таблиц не существует, они создаются
            self.cur.execute("""CREATE TABLE tracks (id         INTEGER, name       STRING, path       STRING, 
            popularity INTEGER DEFAULT (0));""")
            self.cur.execute("""CREATE TABLE favourit (id, name STRING);""")

            self.cur.execute("""CREATE TABLE playlists (name STRING);""")
        dir = str(QFileDialog.getExistingDirectory(self, "Select Directory"))
        id = 0
        for rootdir, dirs, files in os.walk(dir):
            for file in files:
                if (
                        file.split('.')[
                            -1]) == self.track_format:  # в этой строке можно легко изменить формат искмого файла :)
                    tex = fr'{rootdir}\{file}'
                    file = ''.join(file.split('.')[:-1])
                    file = file.replace('"', '')
                    file = file.replace("'", '')
                    file = file.replace('=', ' ')  # Во избежения sql ошибок
                    file = file.replace('?', '')
                    self.cur.execute(f"""INSERT INTO tracks (id, name, path) VALUES({id}, "{file}","{tex}")""")
                    id += 1
        self.con.commit()
        self.listWidget.clear()
        if id > 0:
            for name in self.cur.execute("""SELECT name FROM tracks"""):
                self.listWidget.addItem(str(name[0]))
            self.label_4.setText('Готово!')
        else:
            self.label_4.setText('Ничего не удалось найти')

    def new_item_choosed(self):
        self.seek_track = self.cur.execute(f"""SELECT path FROM tracks WHERE name = 
        '{self.listWidget.currentItem().text()}'""").fetchone()[0]
        self.play()

    def play(self):
        self.time_value.setValue(0)  # обнуляем слайдер
        try:
            self.player.stop()  # Если играет какой то трек - останавливаем это!
        except AttributeError:
            pass
        finally:
            self.pause_btn.setText(self.icons[0])
            name = (self.cur.execute(f"""SELECT name FROM tracks WHERE path = ?""",
                                     (self.seek_track,)).fetchone()[0]).split('.')[0]
            if len(name) > 31:
                name = name[:27] + '...'  # это нужно что бы названия трека не выходило за рамки(с основными шрифтами)
            self.label_4.setText(name)
            self.Instance = vlc.Instance()
            popular = self.cur.execute("""SELECT popularity FROM tracks WHERE path = ?""",
                                       (self.seek_track,)).fetchone()[0] + 1
            self.cur.execute("""UPDATE tracks SET popularity = ? WHERE path = ?""", (popular, self.seek_track))
            self.con.commit()
            if self.cur.execute('SELECT id FROM favourit WHERE id = ?', ((self.cur.execute("""SELECT id FROM tracks 
            WHERE path = ?""", (self.seek_track,))).fetchall()[0])).fetchone():
                self.star.setText('yes')
                self.star.setIcon(PyQt5.Qt.QIcon('img2.png'))
            else:
                self.star.setText('no')
                self.star.setIcon(PyQt5.Qt.QIcon('img.png'))
            self.player = self.Instance.media_player_new()
            media = self.Instance.media_new(self.seek_track)
            self.player.set_media(media)
            self.player.audio_set_volume(self.volume)
            self.update()
            self.player.play()
            events = self.player.event_manager()
            events.event_attach(vlc.EventType.MediaPlayerPositionChanged, self.media_time_changed)
            #  events.event_attach(vlc.EventType.MediaPlayerEndReached(), self.end_reached)

    def end_reached(self):
        pass

    def media_time_changed(self, event):
        self.time_value.setValue(self.player.get_position() * 100)

    def pause(self):
        try:
            self.pause_btn.setText(self.icons[self.icons.index(self.pause_btn.text()) - 1])
            self.player.pause()
        except ValueError:
            pass  # если пользователь без трека наимает на паузу :)

    def past(self):
        try:
            try:
                if self.player.get_time() > 2000:  # от 1 нажатия трек перематывается в начало
                    self.player.stop()  # в влс стоп сбрасывает время к 0
                    self.player.play()
                else:
                    now_in_playlist = [self.listWidget.item(i).text() for i in range(self.listWidget.count())]
                    name = self.seek_track.split('\\')[-1][:-4]
                    name = name.replace('"', '')
                    name = name.replace("'", '')
                    name = name.replace('=', ' ')
                    name = name.replace('?', '')
                    name = name.replace('.', '')  # приводим name в вид как в listWidget
                    if now_in_playlist.index(name) - 1 >= 0:
                        name = now_in_playlist[now_in_playlist.index(name) - 1]
                    else:
                        name = now_in_playlist[-1]
                    self.seek_track = self.cur.execute("""SELECT path FROM tracks WHERE name = ?""",
                                                       (name,)).fetchone()[0]
                    self.play()
            except ValueError:
                if now_in_playlist:
                    self.seek_track = self.cur.execute(f"""SELECT path FROM tracks WHERE name = ?""",
                                                       (now_in_playlist[0],)).fetchone()[0]
                    self.play()
        except AttributeError:
            self.label_4.setText('Ошибка!')  # если пользователь без трека жмет на кнопку

    def next(self):
        try:
            try:
                now_in_playlist = [self.listWidget.item(i).text() for i in range(self.listWidget.count())]
                name = self.seek_track.split('\\')[-1][:-4]  # обрезаем формат
                name = name.replace('"', '')
                name = name.replace("'", '')
                name = name.replace('=', ' ')
                name = name.replace('?', '')
                name = name.replace('.', '')  # приводим name в вид как в listWidget
                if now_in_playlist.index(name) + 1 < len(now_in_playlist):
                    name = now_in_playlist[now_in_playlist.index(name) + 1]
                else:
                    name = now_in_playlist[0]
                self.seek_track = self.cur.execute(f"""SELECT path FROM tracks WHERE name = ?""", (name,)).fetchone()[0]
                self.play()
            except ValueError:
                if now_in_playlist:
                    self.seek_track = self.cur.execute(f"""SELECT path FROM tracks WHERE name = ?""",
                                                       (now_in_playlist[0],)).fetchone()[0]
                    self.play()
        except AttributeError:
            self.label_4.setText('Ошибка!')  # если пользователь без трека жмет на кнопку

    def volume_changed(self, sender):
        try:  # звук изменяется по школе от 0 до 100, где 100 это системная громкость
            if sender.text() == '+':
                self.volume += 5
            else:
                self.volume -= 5
            if self.volume < 0:
                self.volume = 0
            elif self.volume > 100:
                self.volume = 100
            self.player.audio_set_volume(self.volume)
        except AttributeError:
            pass  # если пользователь тыкнет на кнопку, пока ничего нет

    def new_font(self):
        self.setFont(self.fontComboBox.currentFont())

    def new_time(self):
        self.Pressed = True  # Иначе после первого нажатия трек начнёт подстраиваться под слайдер, а не наоборот => бу
        # дут микрозадержки при каждом новом сдивжении слайдера(можно убрать этот флаг и self.released, и запустить, тог
        # да станет ясно, о чём идет речь.
        self.time_value.valueChanged.connect(self.change_time)  # такая казалось бы странная конструкция из 2 функций тр

    def change_time(self, value):
        if self.Pressed:
            self.player.set_position(value / 100)

    def released(self):
        self.Pressed = False

    def dialog(self):
        msgBox = QMessageBox()
        msgBox.setFont(self.fontComboBox.currentFont())
        msgBox.setWindowTitle('Сортировка')
        msgBox.setText('Как именно отсортировать?')
        msgBox.addButton(QPushButton('По алфавиту'), QMessageBox.YesRole)
        msgBox.addButton(QPushButton('По популярности'), QMessageBox.NoRole)
        msgBox.buttonClicked.connect(self.sort_tracks)
        msgBox.exec()

    def sort_tracks(self, btn):
        if 'алфавит' in btn.text().lower():
            now_in_playlist = [self.listWidget.item(i).text() for i in range(self.listWidget.count())]
            self.listWidget.clear()
            now_in_playlist.sort()
            for track in now_in_playlist:
                self.listWidget.addItem(str(track))
        else:
            now_in_playlist = [[self.listWidget.item(i).text()] for i in range(self.listWidget.count())]
            for i in range(len(now_in_playlist)):
                now_in_playlist[i].append(self.cur.execute("""SELECT popularity from tracks WHERE name = ?""",
                                                           (now_in_playlist[i][0],)).fetchone()[0])
            now_in_playlist.sort(key=lambda x: x[1])
            self.listWidget.clear()
            for name in now_in_playlist:
                self.listWidget.addItem(str(name[0]))

    def export(self):
        msgbox = QMessageBox()
        msgbox.setFont(self.fontComboBox.currentFont())
        msgbox.setInformativeText(
            '\t' * 400 + '\n')  # тк у QMessageBox нет толкового изменения размера, я вместо изменения class QMessageBox
        # , создал большой текст, а QMessageBox всегда адаптируется размерами под текст.
        msgbox.setWindowTitle('Сохранение')
        msgbox.setText('Как именно сохранить эти данные??')
        info_table = QTableWidget(msgbox)
        info_table.move(0, 50)
        info_table.setColumnCount(4)
        info_table.resize(650, 700)
        info_table.setHorizontalHeaderLabels(['id', 'name', 'path', 'popularity'])
        try:
            self.res = self.cur.execute("""SELECT id, name, path, popularity FROM tracks""").fetchall()
        except:
            self.res = ['Ещё', 'нет', 'никакой', 'информации']  # на случай, если пользователь будет сохранять ничего
        for i, row in enumerate(self.res):
            info_table.setRowCount(
                info_table.rowCount() + 1)
            for j, elem in enumerate(row):
                info_table.setItem(
                    i, j, QTableWidgetItem(str(elem)))
        msgbox.addButton(QPushButton('В .csv файл'), QMessageBox.YesRole)
        msgbox.addButton(QPushButton('В .sqlite файл'), QMessageBox.NoRole)
        msgbox.addButton(QPushButton('В .txt файл'), QMessageBox.AcceptRole)
        msgbox.addButton(QPushButton('В .json файл'), QMessageBox.ApplyRole)
        msgbox.buttonClicked.connect(self.save)
        msgbox.exec()

    def save(self, btn):
        if 'txt' in btn.text():
            f = open(f'tracks_info_{datetime.datetime.now():%Y-%m-%d_%H-%M}.txt', 'w')  # не думаю, что сохранение нужно
            #  чаще минуты
            f.write('\t'.join(['id', 'name', 'path', '\t', 'popularity']) + '\n')
            for elem in self.res:
                f.write('\t'.join([str(smth) for smth in elem]) + '\n')
            f.close()
            self.label_4.setText('.txt файл успешно создан')
        elif 'sqlite' in btn.text():
            conn = sqlite3.connect(f'tracks_info_{datetime.datetime.now():%Y-%m-%d_%H-%M}.db')
            shutil.copyfile('tracks_list.sqlite', f'tracks_info_{datetime.datetime.now():%Y-%m-%d_%H-%M}.db')
            conn.close()
            self.label_4.setText('.db файл успешно создан')
        elif 'json' in btn.text():
            tex = {'id': [], 'name': [], 'path': [], 'popularity': []}
            for elem in self.res:
                tex['id'].append(elem[0])
                tex['name'].append(elem[1])
                tex['path'].append(elem[2])
                tex['popularity'].append(elem[3])
            with open(f'tracks_info_{datetime.datetime.now():%Y-%m-%d_%H-%M}.json', 'w') as w_file:
                json.dump(tex, w_file, ensure_ascii=False)
            self.label_4.setText('.json файл успешно создан')
        else:
            try:
                data = []
                for elem in self.res:
                    data.append({'id': str(elem[0]), 'name': elem[1], 'path': elem[2], 'popularity': elem[3]})
                with open(f'tracks_info_{datetime.datetime.now():%Y-%m-%d_%H-%M}.csv', 'w', newline='') as f:
                    writer = csv.DictWriter(
                        f, fieldnames=list(data[0].keys()),
                        delimiter=';', quoting=csv.QUOTE_MINIMAL)
                    writer.writeheader()
                    for d in data:
                        writer.writerow(d)
                    self.label_4.setText('.csv файл успешно создан!')
            except IndexError:  # наверняка кто-то захочет попробовать сохранить информацию о ни о чём, .json, .txt,
                # .db в моем коде могут записать ничего, или записать заголовок о отсутствии, а с .csv проще пропустить
                self.label_4.setText('Нет информации.')

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_F10:
            self.pause()
        elif event.key() == QtCore.Qt.Key_Right or event.key() == QtCore.Qt.Key_F11:
            self.next()
        elif event.key() == QtCore.Qt.Key_Left or event.key() == QtCore.Qt.Key_F9:
            self.past()

    def favour(self):
        try:
            if self.star.text() == 'no':  # с помощью no/yes удобно менять картинку
                self.star.setText('yes')
                self.star.setIcon(PyQt5.Qt.QIcon('img2.png'))
                self.cur.execute("""INSERT INTO favourit SELECT id, name FROM tracks WHERE path = ?""",
                                 (self.seek_track,))
                self.con.commit()
            else:
                self.star.setText('no')
                self.cur.execute("""DELETE FROM favourit WHERE id = ?""", (self.cur.execute("""SELECT id FROM tracks  WHERE
                 path = ?""", (self.seek_track,)).fetchone()[0],))
                self.con.commit()
                self.star.setIcon(PyQt5.Qt.QIcon('img.png'))
        except AttributeError:
            self.label_4.setText('Ошибка!')  # пользователь может нажать избранное не включив ничего :)

    def favour_play(self):
        try:
            if self.favoutit_btn.text() == 'Избранное':
                self.playlist_name = 'favourit'
                self.favoutit_btn.setText('Все треки')
                self.listWidget.clear()
                for name in self.cur.execute("""SELECT name FROM favourit"""):
                    self.listWidget.addItem(str(name[0]))
            else:
                self.listWidget.clear()
                self.playlist_name = 'tracks'
                self.favoutit_btn.setText('Избранное')
                for name in self.cur.execute("""SELECT name FROM tracks"""):
                    self.listWidget.addItem(str(name[0]))
            self.now_in_playlist = [self.listWidget.item(i).text() for i in range(self.listWidget.count())]
        except sqlite3.OperationalError:
            self.label_4.setText('Ошибка!')  # если нет избранного

    def search_by_name(self, text):
        try:
            self.listWidget.clear()
            for elem in self.cur.execute(f"""SELECT name FROM {self.playlist_name} WHERE name LIKE ?""", (f'%{text}%',)
                                         ).fetchall():
                self.listWidget.addItem(str(elem[0]))
        except sqlite3.OperationalError:
            pass  # пользователь может захотеть поискать в треках, хотя их еще нет!

    def create_playlist(self):
        try:
            msgbox = QMessageBox()
            msgbox.setFont(self.fontComboBox.currentFont())
            msgbox.setInformativeText(
                '\t' * 385 + '\n')  # тк у QMessageBox нет толкового изменения размера, я вместо изменения класса
            # создал большой текст, а QMessageBox всегда адаптируется размерами под текст.
            msgbox.setWindowTitle('Создание')
            info_table = QTableWidget(msgbox)
            info_table.move(0, 29)
            info_table.setColumnCount(4)
            info_table.resize(650, 712)
            info_table.setHorizontalHeaderLabels(['id', 'name', 'path', 'popularity'])
            self.res = self.cur.execute("""SELECT id, name, path, popularity FROM tracks""").fetchall()
            for i, row in enumerate(self.res):
                info_table.setRowCount(
                    info_table.rowCount() + 1)
                for j, elem in enumerate(row):
                    info_table.setItem(
                        i, j, QTableWidgetItem(str(elem)))
            self.numbers = QLineEdit(msgbox)
            self.numbers.move(0, 740)
            self.numbers.resize(400, 30)
            self.numbers.setPlaceholderText('Введите через пробел id желаемых треков')
            self.name = QLineEdit(msgbox)
            self.name.setPlaceholderText('Введите название плейлиста')
            self.name.resize(400, 30)
            msgbox.addButton(QPushButton('Создать'), QMessageBox.YesRole)
            msgbox.buttonClicked.connect(self.add_playlist)
            msgbox.exec()
        except sqlite3.OperationalError:  # если нет треков
            msgbox = QMessageBox()
            msgbox.setFont(self.fontComboBox.currentFont())
            info = QLabel(msgbox)
            info.resize(300, 20)
            msgbox.setInformativeText('\t' * 7)
            msgbox.setWindowTitle('Ошибка')
            info.setText('Сначала найдите треки!')
            msgbox.addButton(QPushButton('Ясно'), QMessageBox.YesRole)
            msgbox.exec()

    def add_playlist(self):
        tex = self.numbers.text().replace(',', ' ')
        tex = tex.replace('.',
                          ' ')  # я решил, что перестраховка лишней не бывает, добавил элементарные исправления ввода
        ids = [elem.strip() for elem in tex.split()]
        name_of_playlist = self.name.text().strip()
        name_of_playlist = name_of_playlist.replace(' ', '_')
        name_of_playlist = name_of_playlist.replace('"', '')
        name_of_playlist = name_of_playlist.replace("'",
                                                    '')  # замена популярных символов, которые могут выкинуть ошибку
        if self.cur.execute('''SELECT name FROM sqlite_master WHERE type='table' AND name = ?''',
                            (name_of_playlist,)).fetchone():  # проверка на существование данной таблицы.
            self.label_4.setText('Ошибка. Смените название.')
        else:
            try:
                self.cur.execute(f"""CREATE TABLE {name_of_playlist} (id   INTEGER,name STRING);""")
                for elem in ids:
                    elem = int(elem)
                    name = self.cur.execute("""SELECT name FROM tracks WHERE id = ?""", (elem,)).fetchone()[0]
                    self.cur.execute(f"""INSERT into {name_of_playlist} VALUES({elem}, '{name}')""")
                self.cur.execute(f"""INSERT into playlists VALUES('{name_of_playlist}')""")
                self.con.commit()
                self.label_4.setText('Плейлист создан!')
            except TypeError:
                self.label_4.setText('Проверьте корректность ввода!')
                self.cur.execute(f"""DROP TABLE {name_of_playlist}""")
            except sqlite3.OperationalError:
                self.label_4.setText('Проверьте корректность ввода!')

    def open_playlist(self):
        try:
            msgbox = QMessageBox()
            msgbox.setFont(self.fontComboBox.currentFont())
            msgbox.setInformativeText('\t' * 400 + '\n')
            msgbox.setWindowTitle('Ваши плейлисты')
            info_table = QTableWidget(msgbox)
            info_table.move(0, 29)
            info_table.setColumnCount(2)
            info_table.resize(650, 712)
            info_table.itemClicked.connect(self.clicked)
            info = QLabel(msgbox)
            info.resize(600, 20)
            info.setText(' Для выбора плейлиста кликните по его названию(выбранная подборка подсветится)')
            res = []
            info_table.setHorizontalHeaderLabels(['Название', 'Количество треков'])
            tmp = self.cur.execute("""SELECT name FROM playlists""").fetchall()
            for i in range(len(tmp)):
                length = len(self.cur.execute('SELECT id from ' + tmp[i][0]).fetchall())
                res.append([tmp[i][0], length])
            for i, row in enumerate(res):
                info_table.setRowCount(
                    info_table.rowCount() + 1)
                for j, elem in enumerate(row):
                    info_table.setItem(
                        i, j, QTableWidgetItem(str(elem)))
            msgbox.addButton(QPushButton('Открыть'), QMessageBox.YesRole)
            msgbox.addButton(QPushButton('Удалить'), QMessageBox.NoRole)
            msgbox.buttonClicked.connect(self.open_or_delete_playlist)
            msgbox.exec()
        except sqlite3.OperationalError:  # Допустим, вместо названия, пользователь кликнул по кол-ву треков
            msgbox = QMessageBox()
            msgbox.setFont(self.fontComboBox.currentFont())
            msgbox.setWindowTitle('Ошибка')
            msgbox.setInformativeText('\t' * 7)
            info = QLabel(msgbox)
            info.resize(200, 20)
            info.setText('Сначала создайте плейлист')
            msgbox.addButton(QPushButton('Ясно'), QMessageBox.YesRole)
            msgbox.exec()

    def clicked(self, item):
        self.playlist_name = item.text()

    def open_or_delete_playlist(self, sender):
        try:
            if sender.text() == 'Открыть':
                self.listWidget.clear()
                for elem in self.cur.execute("SELECT name FROM " + self.playlist_name):
                    self.listWidget.addItem(elem[0])
                    self.label_4.setText('Успешно открыто')
            elif sender.text() == 'Удалить':
                if self.playlist_name != 'tracks' and self.playlist_name != 'favourit':
                    self.cur.execute(f"""DELETE FROM playlists WHERE name = '{self.playlist_name}'""")
                    self.cur.execute(f"""DROP TABLE {self.playlist_name}""")
                    self.label_4.setText('Плейлист удалён')
                    self.con.commit()
                else:
                    self.cur.execute('Зачем? Я запрещаю!')  # Попытка удалить таблику tracks/favourit
        except sqlite3.OperationalError:
            self.label_4.setText('Выбор некорректен!')

    def paintEvent(self, event):
        try:
            if self.design:
                self.make_decoration()
        except AttributeError:
            pass  # на случай еще не соз
            # данного плеера

    def make_decoration(self):
        colors_for_not_stopped = ['152, 251, 152', '0, 255, 127', '154, 205, 50', '255, 255, 0',
                                  '255, 140, 0']  # чем громче, тем более броский цвет.
        if self.player.get_position != 0:
            index_of_color = round(5 * self.volume / 100) - 1
            if index_of_color < 0:
                index_of_color = 0
            self.setStyleSheet(f"background-color: rgb({colors_for_not_stopped[index_of_color]});")
        if self.pause_btn.text() != '⏸':
            self.setStyleSheet(f"background-color: rgb(240, 230, 140);")
        if self.playlist_name == 'favourit':
            self.label_4.setStyleSheet(f"border: 2px solid Magenta;")
        else:
            self.label_4.setStyleSheet('')

    def start_or_finish_design(self):
        labels = ['Включить оформление', 'Выключить оформление']
        self.design_button.setText(labels[labels.index(self.design_button.text()) - 1])
        self.design = not (self.design)
        if not self.design:
            self.setStyleSheet('')
            self.label_4.setStyleSheet('')

    def format_changed(self, text):
        self.track_format = text


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = Example()
    ex.show()
    sys.exit(app.exec())
