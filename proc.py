import os
os.chdir('pix')
for s in os.listdir():
    if s.endswith('.aria2'):
        t = s[:-6]
        print(s, 'found')
        try:
            os.remove(t)
        except:
            print(t, 'does not exists')
        os.remove(s)
