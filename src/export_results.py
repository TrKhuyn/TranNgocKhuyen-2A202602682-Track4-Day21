"""Package results and REPORT; request a local download from a notebook widget.

The official Colab extension recommends widgets instead of files.download():
https://github.com/googlecolab/colab-vscode/wiki/Known-Issues-and-Workarounds
Widget transport follows the anywidget custom-message API (original implementation):
https://anywidget.dev/en/jupyter-widgets-the-good-parts/
ZIP bytes travel in transient comm buffers rather than notebook output or widget
state, keeping the saved notebook small. No raw datasets or credentials are exported.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import zipfile


def make_archive(root, destination):
    root, destination = Path(root).resolve(), Path(destination).resolve()
    files = sorted(p for p in (root / 'results').rglob('*') if p.is_file())
    report = root / 'report/REPORT.md'
    if not files or not report.is_file():
        raise FileNotFoundError('Run the benchmark and write_report before exporting')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files + [report]:
            if path.resolve() == destination or path.suffix in {'.zip', '.pyc'} or '__pycache__' in path.parts:
                continue
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise ValueError(f'Export file is outside repository: {path}')
            archive.write(path, path.relative_to(root).as_posix())
    return destination


DOWNLOAD_JS = r'''
export default {
  render({ model, el }) {
    const button = document.createElement("button");
    button.textContent = "Tải results.zip";
    button.style.cssText = "padding:10px 18px;cursor:pointer";
    const status = document.createElement("p");
    el.append(button, status);
    let chunks = [];
    let received = 0;
    let expected = 0;
    let filename = "results.zip";
    const receive = (message, buffers) => {
      if (message.kind === "start") {
        chunks = []; received = 0;
        expected = message.size; filename = message.name;
      } else if (message.kind === "chunk") {
        for (const data of buffers || []) {
          const bytes = data instanceof ArrayBuffer ? new Uint8Array(data)
            : new Uint8Array(data.buffer, data.byteOffset, data.byteLength);
          chunks.push(bytes.slice()); received += bytes.byteLength;
        }
        status.textContent = `Đã nhận ${(received / 1e6).toFixed(1)} MB`;
      } else if (message.kind === "end") {
        button.disabled = false;
        if (received !== expected) {
          status.textContent = "File nhận chưa đủ; bấm nút để thử lại.";
          return;
        }
        const url = URL.createObjectURL(new Blob(chunks, { type: "application/zip" }));
        const link = document.createElement("a");
        link.href = url; link.download = filename;
        el.append(link); link.click(); link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 60000);
        chunks = [];
        status.textContent = "Đã gửi yêu cầu tải results.zip. Nếu chưa thấy file, bấm nút hoặc dùng Colab Contents > Download.";
      } else if (message.kind === "error") {
        button.disabled = false; status.textContent = message.detail;
      }
    };
    const request = () => {
      button.disabled = true;
      status.textContent = "Đang lấy kết quả từ runtime...";
      model.send({ action: "download" });
    };
    model.on("msg:custom", receive);
    button.addEventListener("click", request);
    // Request the download when the cell renders; leave a retry button available.
    request();
    return () => {
      model.off("msg:custom", receive);
      button.removeEventListener("click", request);
    };
  }
};
'''


def show_download(archive):
    """Requires anywidget in the remote kernel; does not invoke Colab Web UI APIs."""
    import anywidget
    from IPython.display import display

    path = Path(archive).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)

    class ResultsDownload(anywidget.AnyWidget):
        _esm = DOWNLOAD_JS

        def __init__(self):
            super().__init__()
            self.on_msg(self._download)

        def _download(self, widget, message, buffers):
            if message.get('action') != 'download':
                return
            try:
                self.send(dict(kind='start', name=path.name, size=path.stat().st_size))
                with path.open('rb') as stream:
                    while chunk := stream.read(1024 * 1024):
                        self.send(dict(kind='chunk'), buffers=[chunk])
                self.send(dict(kind='end'))
            except OSError as error:
                self.send(dict(kind='error', detail=str(error)))

    widget = ResultsDownload()
    display(widget)
    return widget


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--root', default='.', help='Repository containing results/ and report/REPORT.md')
    parser.add_argument('--out', default='results.zip', help='ZIP path; ignored by repository .gitignore')
    args = parser.parse_args()
    archive = make_archive(args.root, args.out)
    print(f'Exported {archive.name}: {archive.stat().st_size / 1e6:.1f} MB')


if __name__ == '__main__':
    main()
