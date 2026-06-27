# KathTrimmer — Hướng dẫn sử dụng

## Giới thiệu
**KathTrimmer** là ứng dụng cắt/tách/nén video chạy trên Windows.  
- **Cắt đoạn (Trim)**: Xuất 1 đoạn cụ thể, không mất chất lượng.  
- **Tách đôi (Split)**: Chia video thành 2 phần tại điểm bạn chọn.  
- **Nén video (Compress)**: Giảm dung lượng file bằng H.264 / H.265.

---

## Yêu cầu: Tải FFmpeg

KathTrimmer cần **ffmpeg.exe** và **ffprobe.exe** để hoạt động.

### Cách tải FFmpeg:

1. Mở trang: https://www.gyan.dev/ffmpeg/builds/
2. Tải file **`ffmpeg-release-essentials.zip`**
3. Giải nén, vào thư mục `bin/`
4. Copy **`ffmpeg.exe`** và **`ffprobe.exe`** vào thư mục:
   ```
   KathTrimmer\ffmpeg_bin\
   ```

---

## Hướng dẫn Khởi chạy 🚀

Bạn có thể chạy ứng dụng bằng 3 cách dưới đây:

### Cách 1: Chạy bằng Shortcut an toàn `KathTrimmer.lnk` (KHUYÊN DÙNG)
- Double-click vào file shortcut **`KathTrimmer`** ở thư mục gốc (có icon xanh tím).
- Đây là cách tốt nhất trên Windows vì nó sử dụng trình thông dịch Python hệ thống, không bị tính năng **Smart App Control** hay **Windows Defender** chặn báo lỗi không an toàn (unsafe).
- Để tiện sử dụng, hãy click chuột phải vào shortcut này và chọn **Pin to taskbar** (Ghim vào thanh tác vụ).

### Cách 2: Chạy bằng file Launcher `KathTrimmer.exe`
- Đúp chuột vào file **`KathTrimmer.exe`** ở thư mục gốc để mở ứng dụng ngay lập tức mà không cần terminal.
- *Lưu ý*: File EXE tự build chưa ký số có thể bị Windows Smart App Control chặn. Nếu bị chặn, vui lòng sử dụng **Cách 1**.

### Cách 3: Chạy trực tiếp bằng dòng lệnh (Development)
```bash
python main.py
```

---

## Cách Build ứng dụng (Tạo lại Launcher)

1. Tải và cài đặt các thư viện phụ thuộc:
   ```bash
   pip install -r requirements.txt
   ```
2. Chạy file script:
   ```bash
   build.bat
   ```
   Script sẽ tự động biên dịch lại file launcher và tạo shortcut gán sẵn AppUserModelID để tối ưu hóa hiển thị taskbar.

---

## Tính năng

| Chức năng | Mô tả | Chất lượng |
|---|---|---|
| Trim (Cắt đoạn) | Cắt 1 đoạn từ video | 🟢 Lossless |
| Split (Tách đôi) | Chia video làm 2 file | 🟢 Lossless |
| Compress (Nén) | Giảm dung lượng file | 🟡 Gần lossless (CRF 18-28) |

---

## Cấu trúc thư mục

```
KathTrimmer/
├── main.py
├── ui/
│   ├── app.py
│   ├── drop_zone.py
│   ├── timeline.py
│   └── theme.py
├── core/
│   ├── ffmpeg_runner.py
│   └── video_info.py
├── ffmpeg_bin/       ← đặt ffmpeg.exe + ffprobe.exe vào đây
├── assets/
│   └── icon.ico
├── build.bat
└── requirements.txt
```
