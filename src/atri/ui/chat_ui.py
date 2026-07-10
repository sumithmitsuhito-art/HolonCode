from PySide6 import QtCore, QtGui, QtWidgets


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(850, 600)

        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.centralwidget)
        self.verticalLayout_2.setObjectName("verticalLayout_2")

        self.title_label = QtWidgets.QLabel(self.centralwidget)
        font = QtGui.QFont()
        font.setPointSize(18)
        font.setBold(True)
        self.title_label.setFont(font)
        self.title_label.setAlignment(QtCore.Qt.AlignCenter)
        self.title_label.setObjectName("title_label")
        self.verticalLayout_2.addWidget(self.title_label)

        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")

        self.knowledge_combo = QtWidgets.QComboBox(self.centralwidget)
        self.knowledge_combo.setObjectName("knowledge_combo")
        self.horizontalLayout.addWidget(self.knowledge_combo)

        self.start_btn = QtWidgets.QPushButton(self.centralwidget)
        self.start_btn.setObjectName("start_btn")
        self.horizontalLayout.addWidget(self.start_btn)

        self.verticalLayout_2.addLayout(self.horizontalLayout)

        self.chat_display = QtWidgets.QTextEdit(self.centralwidget)
        self.chat_display.setReadOnly(True)
        self.chat_display.setObjectName("chat_display")
        self.verticalLayout_2.addWidget(self.chat_display)

        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")

        self.input_edit = QtWidgets.QLineEdit(self.centralwidget)
        self.input_edit.setObjectName("input_edit")
        self.horizontalLayout_2.addWidget(self.input_edit)

        self.send_btn = QtWidgets.QPushButton(self.centralwidget)
        self.send_btn.setEnabled(False)
        self.send_btn.setObjectName("send_btn")
        self.horizontalLayout_2.addWidget(self.send_btn)

        self.verticalLayout_2.addLayout(self.horizontalLayout_2)

        MainWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "C-Tutor AI · C语言导师"))
        self.title_label.setText(_translate("MainWindow", "💻 C-Tutor AI · C语言导师"))
        self.start_btn.setText(_translate("MainWindow", "🎯 开始教学"))
        self.input_edit.setPlaceholderText(_translate("MainWindow", "输入消息，按回车发送..."))
        self.send_btn.setText(_translate("MainWindow", "发送"))