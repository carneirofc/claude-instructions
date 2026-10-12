#include "commandrunner.h"

#include <QStandardPaths>

#include <KLocalizedString>

CommandRunner::CommandRunner(QObject *parent)
    : QObject(parent)
{
    m_kill.setSingleShot(true);
    m_kill.setInterval(3000);
    connect(&m_kill, &QTimer::timeout, &m_process, &QProcess::kill);
    connect(&m_process, &QProcess::stateChanged, this, &CommandRunner::runningChanged);
    connect(&m_process, &QProcess::readyReadStandardOutput, this, [this] { drain(QProcess::StandardOutput); });
    connect(&m_process, &QProcess::readyReadStandardError, this, [this] { drain(QProcess::StandardError); });
    connect(&m_process, &QProcess::finished, this, [this](int code, QProcess::ExitStatus status) {
        m_kill.stop();
        if (status == QProcess::CrashExit) {
            Q_EMIT finished(-1, i18n("%1 stopped", m_label));
        } else if (code == 0) {
            Q_EMIT finished(0, i18n("%1 finished", m_label));
        } else {
            Q_EMIT finished(code, i18n("%1 failed with exit code %2", m_label, code));
        }
    });
    connect(&m_process, &QProcess::errorOccurred, this, [this](QProcess::ProcessError error) {
        if (error == QProcess::FailedToStart) {
            Q_EMIT finished(-1, i18n("Could not start %1: %2", m_label, m_process.errorString()));
        }
    });
}

bool CommandRunner::start(const QStringList &command, const QString &workingDirectory)
{
    if (running() || command.isEmpty()) {
        return false;
    }
    const QString program = QStandardPaths::findExecutable(command.first());
    if (program.isEmpty()) {
        Q_EMIT finished(-1, i18n("%1 is not installed", command.first()));
        return false;
    }
    m_label = command.join(QLatin1Char(' '));
    m_output.clear();
    m_partial[0].clear();
    m_partial[1].clear();
    Q_EMIT outputChanged();
    m_process.setWorkingDirectory(workingDirectory);
    m_process.start(program, command.mid(1));
    return true;
}

void CommandRunner::stop()
{
    if (running()) {
        m_process.terminate();
        m_kill.start();
    }
}

void CommandRunner::drain(QProcess::ProcessChannel channel)
{
    m_process.setReadChannel(channel);
    QByteArray &partial = m_partial[channel == QProcess::StandardError];
    partial += m_process.readAll();
    qsizetype newline;
    while ((newline = partial.indexOf('\n')) >= 0) {
        m_output.append(QString::fromUtf8(partial.left(newline)));
        partial.remove(0, newline + 1);
    }
    Q_EMIT outputChanged();
}
