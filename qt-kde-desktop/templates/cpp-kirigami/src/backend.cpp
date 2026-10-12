#include "backend.h"

#include <QDesktopServices>
#include <QDir>
#include <QDirIterator>
#include <QFileInfo>
#include <QLocale>
#include <QMimeDatabase>
#include <QtConcurrent>

#include <KIO/OpenFileManagerWindowJob>
#include <KLocalizedString>

#include "myappconfig.h"

using namespace Qt::Literals::StringLiterals;

namespace
{
const QStringList imageSuffixes{u"jpg"_s, u"jpeg"_s, u"png"_s, u"webp"_s, u"gif"_s, u"bmp"_s,
                                u"tif"_s, u"tiff"_s};

// Runs on a QThreadPool thread: no QObject, only values.
QList<FileEntry> listFolder(const QString &folder, bool showHidden)
{
    QMimeDatabase mimes;  // thread-safe
    QDir::Filters filters = QDir::AllEntries | QDir::NoDotAndDotDot;
    if (showHidden) {
        filters |= QDir::Hidden;
    }
    QList<FileEntry> entries;
    const auto infos = QDir(folder).entryInfoList(filters, QDir::DirsFirst | QDir::Name | QDir::IgnoreCase);
    for (const QFileInfo &info : infos) {
        const auto mime = mimes.mimeTypeForFile(info, QMimeDatabase::MatchExtension);
        entries.append({info.absoluteFilePath(), info.fileName(),
                        info.isDir() ? u"folder"_s : mime.iconName(), info.size(), info.isDir(),
                        !info.isDir() && imageSuffixes.contains(info.suffix().toLower())});
    }
    return entries;
}
}

int FolderModel::rowCount(const QModelIndex &parent) const
{
    return parent.isValid() ? 0 : int(m_entries.size());
}

QHash<int, QByteArray> FolderModel::roleNames() const
{
    return {{PathRole, "path"}, {TitleRole, "title"}, {SubtitleRole, "subtitle"},
            {IconNameRole, "iconName"}, {ThumbnailRole, "thumbnail"}, {IsFolderRole, "isFolder"}};
}

QVariant FolderModel::data(const QModelIndex &index, int role) const
{
    if (!checkIndex(index, CheckIndexOption::IndexIsValid)) {
        return {};
    }
    const FileEntry &e = m_entries.at(index.row());
    switch (role) {
    case PathRole: return e.path;
    case Qt::DisplayRole:
    case TitleRole: return e.name;
    case SubtitleRole: return e.isDir ? i18n("Folder") : QLocale().formattedDataSize(e.size);
    case IconNameRole: return e.iconName;
    case ThumbnailRole:
        return e.isImage ? u"image://thumbs/"_s + QString::fromLatin1(e.path.toUtf8().toBase64(
                               QByteArray::Base64UrlEncoding))
                         : QString();
    case IsFolderRole: return e.isDir;
    }
    return {};
}

void FolderModel::setEntries(QList<FileEntry> entries)
{
    beginResetModel();
    m_entries = std::move(entries);
    endResetModel();
    Q_EMIT countChanged();
}

QString FolderModel::pathAt(int row) const
{
    return row >= 0 && row < m_entries.size() ? m_entries.at(row).path : QString();
}

Backend::Backend(QObject *parent)
    : QObject(parent)
{
    connect(&m_scan, &QFutureWatcherBase::started, this, &Backend::busyChanged);
    connect(&m_scan, &QFutureWatcherBase::finished, this, [this] {
        Q_EMIT busyChanged();
        m_model.setEntries(m_scan.result());
    });
    connect(&m_runner, &CommandRunner::finished, this, [this](int code, const QString &summary) {
        if (code == 0) {
            Q_EMIT message(summary);
        } else {
            Q_EMIT problem(summary);
        }
    });
    open(QDir::homePath());
}

QString Backend::title() const
{
    const QString name = QFileInfo(m_folder).fileName();
    return name.isEmpty() ? u"/"_s : name;
}

void Backend::open(const QString &path)
{
    if (!QFileInfo(path).isDir()) {
        Q_EMIT problem(i18n("%1 is not a folder", path));
        return;
    }
    m_folder = QDir(path).absolutePath();
    Q_EMIT folderChanged();
    // QtConcurrent::run cannot be cancelled; setFuture() stops watching the older scan, so
    // its result is simply never shown.
    m_scan.setFuture(QtConcurrent::run(listFolder, m_folder, Config::self()->showHidden()));
}

void Backend::openUrl(const QUrl &url)
{
    const QFileInfo info(url.toLocalFile());
    open(info.isDir() ? info.absoluteFilePath() : info.absolutePath());
}

void Backend::up()
{
    QDir dir(m_folder);
    if (dir.cdUp()) {
        open(dir.absolutePath());
    }
}

void Backend::activate(int row)
{
    const QString path = m_model.pathAt(row);
    if (QFileInfo(path).isDir()) {
        open(path);
    } else if (!path.isEmpty()) {
        QDesktopServices::openUrl(QUrl::fromLocalFile(path));  // the user's default app
    }
}

void Backend::reveal(int row)
{
    if (const QString path = m_model.pathAt(row); !path.isEmpty()) {
        KIO::highlightInFileManager({QUrl::fromLocalFile(path)});  // FileManager1, with fallback
    }
}

void Backend::runCommand(int row)
{
    if (const QString path = m_model.pathAt(row); !path.isEmpty()) {
        QStringList command = QProcess::splitCommand(Config::self()->command());
        command.append(path);
        m_runner.start(command, m_folder);
    }
}
