#!/bin/bash
# ==============================================================================
# Share Script - Otomatisasi Checksheet Team (Zul, Iqbal, Rama, Yogi)
# ==============================================================================

PORT=8000
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')

echo "=========================================================="
echo "   🚀 OTOMATISASI CHECKSHEET - TEAM SHARING TOOL"
echo "=========================================================="
echo "Tim: Zul, Iqbal, Rama, Yogi"
echo ""

# Check if web server is running on port 8000
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null ; then
    echo "✅ Server aktif dan berjalan di port $PORT."
else
    echo "⚠️  Server belum berjalan di port $PORT."
    read -p "Nyalakan server sekarang? (y/n): " start_srv
    if [[ "$start_srv" == "y" || "$start_srv" == "Y" ]]; then
        echo "Menjalankan server di background..."
        .venv/bin/python run_server.py > /dev/null 2>&1 &
        sleep 2
        echo "✅ Server berhasil dinyalakan!"
    else
        echo "Silakan jalankan 'python run_server.py' terlebih dahulu."
        exit 1
    fi
fi

echo ""
echo "----------------------------------------------------------"
echo "PILIHAN KONEKSI UNTUK TIM:"
echo "----------------------------------------------------------"
echo "1. Jaringan Wi-Fi / Kantor Sama (LAN)"
echo "   URL: http://${LOCAL_IP:-127.0.0.1}:$PORT"
echo ""
echo "2. Internet Publik / WFH (Cloudflare Tunnel)"
echo "   Bisa diakses dari mana saja tanpa perlu 1 Wi-Fi"
echo "----------------------------------------------------------"
echo ""

read -p "Pilih mode sharing (1=LAN, 2=Cloudflare Tunnel, q=Keluar): " choice

case $choice in
    1)
        echo ""
        echo "🎉 Bagikan link ini ke Zul, Iqbal, Rama, dan Yogi:"
        echo ""
        echo "👉  http://${LOCAL_IP:-127.0.0.1}:$PORT"
        echo ""
        echo "Catatan: Pastikan laptop tim terhubung ke Wi-Fi yang sama."
        ;;
    2)
        if command -v cloudflared &> /dev/null; then
            echo ""
            echo "🌐 Menjalankan Cloudflare Tunnel ke http://localhost:$PORT..."
            echo "Tunggu beberapa detik sampai URL https://...trycloudflare.com muncul di bawah:"
            echo ""
            cloudflared tunnel --url http://localhost:$PORT
        else
            echo ""
            echo "❌ 'cloudflared' belum terinstall."
            echo "Instalasi mudah dengan: brew install cloudflared"
            echo "Atau gunakan koneksi Wi-Fi lokal: http://${LOCAL_IP:-127.0.0.1}:$PORT"
        fi
        ;;
    *)
        echo "Selesai."
        ;;
esac
