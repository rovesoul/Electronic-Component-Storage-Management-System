电子元器件管理系统

> python 配合 sqlite 写的单机版电子元器件管理系统，共享用！

- warehouse_main.py 是本地数据库软件，单文件运行；

- dbapi.py 是数据库接口，单文件运行；

```
pyinstaller --onefile main.py --add-data 'config.json:.' --add-data 'components.db:.' --add-data 'dbapi.py:.' --add-data 'src:src' --windowed;
```

```
pyinstaller main.py --icon=logo.png --add-data 'src:.' --add-data 'config.json:.' --add-data 'dbapi.py:.' --add-data 'components.db:.'
```

pyinstaller main.py --noconsole --icon=logo.png --add-data 'src:.' --add-data 'config.json:.' --add-data 'dbapi.py:.' --add-data 'components.db:.'
