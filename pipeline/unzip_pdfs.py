import zipfile, glob, os, sys
OUT = 'PDF原始檔'
os.makedirs(OUT, exist_ok=True)
n = bad = 0
for z in sorted(glob.glob('科展資料庫-*.zip')):
    with zipfile.ZipFile(z) as zf:
        for info in zf.infolist():
            name = info.filename
            if info.flag_bits & 0x800 == 0:
                try: name = name.encode('cp437').decode('utf-8')
                except Exception: pass
            if info.is_dir() or '/._' in name or name.startswith('._'):
                continue
            dest = os.path.join(OUT, name)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            try:
                with zf.open(info) as src, open(dest, 'wb') as dst:
                    while True:
                        b = src.read(1 << 20)
                        if not b: break
                        dst.write(b)
                n += 1
            except Exception as e:
                bad += 1; print('BAD', z, name, e, flush=True)
    print('done', z, n, flush=True)
print('FINISHED', n, 'bad', bad, flush=True)
