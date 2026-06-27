type UpdateDialogProps = {
  currentVersion: string;
  latestVersion: string;
  onCancel: () => void;
  onConfirm: () => void;
};

export function UpdateDialog({
  currentVersion,
  latestVersion,
  onCancel,
  onConfirm,
}: UpdateDialogProps) {
  return (
    <div className="update-dialog-overlay" role="presentation">
      <section
        className="update-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="update-dialog-title"
        aria-describedby="update-dialog-description"
      >
        <h2 id="update-dialog-title">发现新版本</h2>
        <p className="update-dialog-versions">
          当前版本 {currentVersion}
          <span aria-hidden="true"> → </span>
          最新版本 {latestVersion}
        </p>
        <p id="update-dialog-description" className="update-dialog-description">
          点击“下载并安装”后，会自动下载适合当前电脑的安装包并打开安装程序。安装后，原来的宠物和设置会保留。
        </p>
        <div className="update-dialog-actions">
          <button type="button" onClick={onCancel}>
            稍后再说
          </button>
          <button type="button" onClick={onConfirm} autoFocus>
            下载并安装
          </button>
        </div>
      </section>
    </div>
  );
}
