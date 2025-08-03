создай секрет `SPACES` и добавь в него ссылки на спейсы вида: `https://huggingface.co/spaces/user/space`, каждую с новой строки. не используй прямые ссылки вида `https://user-space.hf.space`. внимание: не забудь указать в список и адрес самого спейса с этим кодом!

эндпоинты:
- `https://user-space.hf.space/` - главная страница с заглушкой<sup>!</sup> и информацией о состоянии в самом низу

- `https://user-space.hf.space/status.json` - информация о состоянии спейсов в формате JSON

можно задать интервал пробуждения в часах в `app.py`: `UPDATE_INTERVAL_IN_HOURS`, по умолчанию 10 (±1 минута).

для доступа к своим **закрытым** спейсам можно подгрузить состояние браузера из файла, для этого рядом с `app.py` должен быть `state.json`, см. [save_storage_state.py](https://github.com/imbecility/hfawaker/blob/main/save_storage_state.py).

<sup>!</sup> заглушка меняется в Dockerfile (любое репо с index.html клонируемое в static). не обязательно.

