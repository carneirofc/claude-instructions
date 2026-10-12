#pragma once

#include <QAbstractListModel>
#include <QFutureWatcher>
#include <QObject>
#include <QQmlEngine>
#include <QUrl>

#include "commandrunner.h"

struct FileEntry {
    QString path;
    QString name;
    QString iconName;
    qint64 size = 0;
    bool isDir = false;
    bool isImage = false;
};

// The folder as a list model: role names are the delegates' required properties.
class FolderModel : public QAbstractListModel
{
    Q_OBJECT
    QML_ELEMENT
    QML_UNCREATABLE("Provided by Backend.folder")
    Q_PROPERTY(int count READ rowCount NOTIFY countChanged FINAL)

public:
    enum Role { PathRole = Qt::UserRole + 1, TitleRole, SubtitleRole, IconNameRole,
                ThumbnailRole, IsFolderRole };
    Q_ENUM(Role)

    using QAbstractListModel::QAbstractListModel;
    int rowCount(const QModelIndex &parent = {}) const override;
    QVariant data(const QModelIndex &index, int role) const override;
    QHash<int, QByteArray> roleNames() const override;

    void setEntries(QList<FileEntry> entries);
    QString pathAt(int row) const;

Q_SIGNALS:
    void countChanged();

private:
    QList<FileEntry> m_entries;
};

// The one object QML talks to: `Backend.open(...)`, `Backend.folder`, ...
class Backend : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(QString folderPath READ folderPath NOTIFY folderChanged FINAL)
    Q_PROPERTY(QString title READ title NOTIFY folderChanged FINAL)
    Q_PROPERTY(bool busy READ busy NOTIFY busyChanged FINAL)
    Q_PROPERTY(FolderModel *folder READ folder CONSTANT FINAL)
    Q_PROPERTY(CommandRunner *command READ command CONSTANT FINAL)

public:
    explicit Backend(QObject *parent = nullptr);

    QString folderPath() const { return m_folder; }
    QString title() const;
    bool busy() const { return m_scan.isRunning(); }
    FolderModel *folder() { return &m_model; }
    CommandRunner *command() { return &m_runner; }

    Q_INVOKABLE void open(const QString &path);
    Q_INVOKABLE void openUrl(const QUrl &url);
    Q_INVOKABLE void up();
    Q_INVOKABLE void activate(int row);
    Q_INVOKABLE void reveal(int row);
    Q_INVOKABLE void runCommand(int row);

Q_SIGNALS:
    void folderChanged();
    void busyChanged();
    void message(const QString &text);
    void problem(const QString &text);

private:
    QString m_folder;
    FolderModel m_model;
    CommandRunner m_runner;
    QFutureWatcher<QList<FileEntry>> m_scan;
};
