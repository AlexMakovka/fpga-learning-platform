FROM ubuntu:24.04

# Неінтерактивний режим використовується лише під час встановлення
# системних пакетів і не зберігається як постійна змінна середовища.
ARG DEBIAN_FRONTEND=noninteractive

# Образ містить інструменти HDL-перевірки:
# Icarus Verilog — компіляція Verilog,
# VVP — моделювання скомпільованого коду,
# Verilator — статичний lint-аналіз,
# Yosys — синтез HDL-опису.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        iverilog \
        verilator \
        yosys \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Робочий каталог використовується для тимчасово підключених
# HDL-файлів, testbench і результатів перевірки.
WORKDIR /workspace

# Безпечна команда за замовчуванням дозволяє перевірити наявність
# Icarus Verilog. Під час реальної перевірки команда контейнера
# перевизначається серверною частиною системи.
CMD ["iverilog", "-V"]