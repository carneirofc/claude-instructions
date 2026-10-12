#include "thumbnailprovider.h"

#include <QCryptographicHash>
#include <QDir>
#include <QFileInfo>
#include <QImageReader>
#include <QImageWriter>
#include <QRunnable>
#include <QSaveFile>
#include <QStandardPaths>

namespace
{
constexpr int buckets[] = {64, 128, 192, 256, 384, 512, 768, 1024};

int bucket(int edge)
{
    for (int b : buckets) {
        if (b >= edge) {
            return b;
        }
    }
    return 1024;
}

QString cachePath(const QFileInfo &source, int edge)
{
    const QByteArray raw = source.absoluteFilePath().toUtf8() + '\0'
        + QByteArray::number(source.lastModified().toMSecsSinceEpoch()) + '\0'
        + QByteArray::number(source.size()) + '\0' + QByteArray::number(edge);
    const QString key = QString::fromLatin1(QCryptographicHash::hash(raw, QCryptographicHash::Blake2s_128).toHex());
    return QStandardPaths::writableLocation(QStandardPaths::CacheLocation) + QLatin1String("/thumbnails/")
        + key.left(2) + QLatin1Char('/') + key + QLatin1String(".webp");
}

QImage thumbnail(const QString &path, int edge)
{
    const QFileInfo source(path);
    const QString cached = cachePath(source, edge);
    if (QImage hit(cached); !hit.isNull()) {
        return hit;
    }
    QImageReader reader(path);
    reader.setAutoTransform(true);  // EXIF orientation
    const QSize full = reader.size();
    if (full.isValid()) {
        reader.setScaledSize(full.scaled(edge, edge, Qt::KeepAspectRatio));  // decode small
    }
    QImage image = reader.read();
    if (image.isNull()) {
        return image;
    }
    QDir().mkpath(QFileInfo(cached).absolutePath());
    QSaveFile out(cached);  // atomic: write to a temp file, rename on commit
    if (out.open(QIODevice::WriteOnly)) {
        QImageWriter writer(&out, "webp");  // needs qt6-imageformats
        writer.setQuality(80);
        if (writer.write(image)) {
            out.commit();
        }
    }
    return image;
}

class Response : public QQuickImageResponse, public QRunnable
{
public:
    Response(QString path, int edge)
        : m_path(std::move(path))
        , m_edge(edge)
    {
        setAutoDelete(false);  // QML deletes the response, not the pool
    }
    void run() override
    {
        if (!m_cancelled.loadAcquire()) {
            m_image = thumbnail(m_path, m_edge);
        }
        Q_EMIT finished();
    }
    QQuickTextureFactory *textureFactory() const override
    {
        return QQuickTextureFactory::textureFactoryForImage(m_image);
    }
    void cancel() override { m_cancelled.storeRelease(1); }

private:
    QString m_path;
    int m_edge;
    QImage m_image;
    QAtomicInt m_cancelled;
};
}

ThumbnailProvider::ThumbnailProvider()
{
    m_pool.setMaxThreadCount(qBound(2, QThread::idealThreadCount() / 2, 6));
}

QQuickImageResponse *ThumbnailProvider::requestImageResponse(const QString &id, const QSize &requestedSize)
{
    const QString path = QString::fromUtf8(QByteArray::fromBase64(id.toLatin1(), QByteArray::Base64UrlEncoding));
    const int edge = bucket(requestedSize.isValid() ? qMax(requestedSize.width(), requestedSize.height()) : 256);
    auto *response = new Response(path, edge);
    m_pool.start(response);
    return response;
}
