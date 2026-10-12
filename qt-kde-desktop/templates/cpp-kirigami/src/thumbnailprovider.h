#pragma once

#include <QQuickAsyncImageProvider>
#include <QThreadPool>

// image://thumbs/<base64url path>: decode at the requested size (QImageReader scales JPEG
// in the decoder), cache as WebP under ~/.cache/myapp/thumbnails, serve the cache after.
// Work runs on a private QThreadPool; QML never waits on the GUI thread.
class ThumbnailProvider : public QQuickAsyncImageProvider
{
public:
    ThumbnailProvider();
    QQuickImageResponse *requestImageResponse(const QString &id, const QSize &requestedSize) override;

private:
    QThreadPool m_pool;
};
