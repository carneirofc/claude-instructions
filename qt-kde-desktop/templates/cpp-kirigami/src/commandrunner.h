#pragma once

#include <QObject>
#include <QProcess>
#include <QQmlEngine>
#include <QStringList>
#include <QTimer>

// An external command, asynchronous on the GUI thread: output streams through signals.
// Argument lists only, never a shell string; SIGTERM, then SIGKILL after a grace period.
class CommandRunner : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_UNCREATABLE("Provided by Backend.command")
    Q_PROPERTY(bool running READ running NOTIFY runningChanged FINAL)
    Q_PROPERTY(QStringList output READ output NOTIFY outputChanged FINAL)

public:
    explicit CommandRunner(QObject *parent = nullptr);

    bool running() const { return m_process.state() != QProcess::NotRunning; }
    QStringList output() const { return m_output; }
    bool start(const QStringList &command, const QString &workingDirectory = {});
    Q_INVOKABLE void stop();

Q_SIGNALS:
    void runningChanged();
    void outputChanged();
    void finished(int exitCode, const QString &summary);  // -1: crashed or failed to start

private:
    void drain(QProcess::ProcessChannel channel);

    QProcess m_process;
    QTimer m_kill;
    QStringList m_output;
    QByteArray m_partial[2];
    QString m_label;
};
