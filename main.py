import random
from prettytable import PrettyTable

# Параметры системы
NUM_PROCESSORS = 4
MEM_SIZE = 16  # 16 ячеек по 1 байт
CACHE_LINE_SIZE = 2  # Размер строки кэша 8 бит
CACHE_WAYS = 2  # Ассоциативность кэша 2
CACHE_SETS = 4  # 4 строки кэша

# Состояния строки кэша
INVALID = 0
SHARED = 1
EXCLUSIVE = 2
MODIFIED = 3
RECENT = 4
TAGGED = 5

states = {
    0: 'INVALID',
    1: 'SHARED',
    2: 'EXCLUSIVE',
    3: 'MODIFIED',
    4: 'RECENT',
    5: 'TAGGED'
}


# Класс строки кэша
class CacheLine:
    # линия кеша имеет тэг(адрес в главной памяти) дата(значение) и один из 6 стейтов
    def __init__(self):
        self.tag = 0
        self.data = 0
        self.state = INVALID


class MainMemory:
    # прост массив ячеек
    def __init__(self):
        self.data = [0] * MEM_SIZE


# Класс кэша
class Cache:
    # прост массив линий кэша
    def __init__(self):
        self.lines = [CacheLine() for _ in range(CACHE_SETS)]

    # возвращает линию с нужным тэгом
    def get_line(self, address):
        for line in self.lines:
            if line.state != INVALID and line.tag == address:
                return line
        return None


class Processor:
    global processors, memory, time, commands_amount, system_states
    system_states = {}

    def change_time_n_save_state(self, delta):
        global time
        time += delta
        system_states[time] = get_system_state()

    def __init__(self, id, cache, memory):
        # привязка с соответсвующему кэшу и к главной памяти
        self.id = id
        self.cache = cache
        self.main_memory = memory

    def rewrite_cacheline(self, tag, data, state):
        global time, commands_amount
        if tag % CACHE_WAYS == 0:
            arr = self.cache.lines[0: CACHE_SETS // CACHE_WAYS - 1]
        else:
            arr = self.cache.lines[CACHE_SETS // CACHE_WAYS: CACHE_SETS - 1]
        # если есть инвалидная строка - пишем в неё
        for line in arr:
            if line.state == INVALID:
                line_to_write = line
                break
        else:
            # иначе радномную удаляем
            if tag % CACHE_WAYS == 0:
                evicted_line = self.cache.lines[
                    random.randint(0, CACHE_SETS // CACHE_WAYS - 1)]
            else:
                evicted_line = self.cache.lines[
                    random.randint(CACHE_SETS // CACHE_WAYS, CACHE_SETS - 1)]
            if evicted_line.state == TAGGED or evicted_line.state == MODIFIED:
                # сохраняем в мейн память если надо
                self.main_memory.data[evicted_line.tag] = evicted_line.data
                print(
                    f'Процессор {self.id} убрал из кэша линию {self.cache.lines.index(evicted_line)} отправив данные в основную память')
            else:
                print(
                    f'Процессор {self.id} убрал из кэша линию  {self.cache.lines.index(evicted_line)}')
            evicted_line.state = INVALID
            line_to_write = evicted_line
        # записываем данные
        print(
            f'Процессор {self.id} записывает данные {data} в линию {self.cache.lines.index(line_to_write)} с тегом {bin(tag//2)} и состоянием {states[state]}')
        line_to_write.tag = tag
        line_to_write.data = data
        line_to_write.state = state
        if len(commands_amount) == 0 or self.id == commands_amount[-1]:
            self.change_time_n_save_state(1)
        # возвращает значение для чтения из других кэшей и флаг который надо к нему поставить

    def read_in_others(self, address):
        print(
            f'Процессор {self.id} отправил по шине запрос о чтении из адреса {bin(address)}')
        global time, bus
        bus += 1
        self.change_time_n_save_state(40)
        others_ids = list(range(NUM_PROCESSORS))
        others_ids.remove(self.id)
        # id всех кроме вызвашего
        for id in others_ids:
            line = processors[id].cache.get_line(address)
            if line is not None and line.state != SHARED:
                print(
                    f'Процессор {id} прерывает и предоставляет данные, т.к. имеет в кэше линию с адресом {bin(address)} в состоянии={states[line.state]}')
                if line.state == MODIFIED or line.state == TAGGED:
                    line.state = SHARED
                    return line.data, TAGGED
                if line.state == EXCLUSIVE or line.state == RECENT:
                    line.state = SHARED
                    return line.data, RECENT
        print('Не было отправлено прерываний от других кэшей')
        return None, EXCLUSIVE

    # возвращает значение для модификации из других кэшей и флаг который надо к нему поставить
    def RWITM_in_others(self, address):
        global time, bus
        self.change_time_n_save_state(40)
        bus += 1
        print(
            f'Процессор {self.id} отправил по шине запрос о чтении из адреса {bin(address)} с намерением изменить данные')
        others_ids = list(range(NUM_PROCESSORS))
        others_ids.remove(self.id)
        for id in others_ids:
            line = processors[id].cache.get_line(address)
            if line is not None and line.state != SHARED:
                print(
                    f'Процессор {id} прерывает и предоставляет данные, т.к. имеет в кэше линию с адресом {bin(address)} в состоянии={states[line.state]}')
                line.state = INVALID
                print(
                    f'Процессор {id} меняет состояние линии {processors[id].cache.lines.index(line)} с адресом {bin(address)} на INVALID')
                self.change_time_n_save_state(20)
                return line.data, MODIFIED
        self.change_time_n_save_state(20)
        print('Не было отправлено прерываний от других кэшей')
        return None, RECENT

    # делает инвалидами все значения с заданным тэгом в других кэшах
    def invalidate_others(self, address):
        print(f'Процессор {self.id} посылает запрос инвалидации')
        global time, bus
        bus += 1
        others_ids = list(range(NUM_PROCESSORS))
        others_ids.remove(self.id)
        for id in others_ids:
            line = processors[id].cache.get_line(address)
            if line is not None:
                print(
                    f'Линия {processors[id].cache.lines.index(line)} с тэгом {bin(line.tag//2)} в кэше процессора {processors[id].id} стала INVALID: {states[line.state]}=>{INVALID} ')
                line.state = INVALID
        self.change_time_n_save_state(40)

    # меняет остальные R на S
    def r_to_s_others(self, address):
        print(f'Процессор {self.id} посылает запрос об изменении состояний RECENT на SHARED')
        global time, bus
        bus += 1
        others_ids = list(range(NUM_PROCESSORS))
        others_ids.remove(self.id)
        for id in others_ids:
            line = processors[id].cache.get_line(address)
            if (line is not None) and (line.state == RECENT):
                print(
                    f'Линия {processors[id].cache.lines.index(line)} с тэгом {bin(line.tag // 2)} в кэше процессора {processors[id].id} стала INVALID: {states[line.state]}=>{INVALID} ')
                line.state = SHARED
        self.change_time_n_save_state(40)

    def read(self, address):
        print('Логи:')
        line = self.cache.get_line(address)
        global time, commands_amount

        if len(commands_amount) == 0 or self.id == commands_amount[0]:
            self.change_time_n_save_state(20)
        # Read Hit
        if line is not None:
            print(
                f"Read hit: Процессор {self.id} имел линию {self.cache.lines.index(line)} с тэгом {bin(address//2)} и состоянием {line.state}")
            if line.state == SHARED:
                self.r_to_s_others(address)
                line.state = RECENT
                print(
                    f'Линия {self.cache.lines.index(line)} с тэгом {bin(address//2)} в кэше процессора {self.id} стала RECENT: SHARED => RECENT')
            if len(commands_amount) == 0 or self.id == commands_amount[-1]:
                self.change_time_n_save_state(20)
            return line.data
        # Read Miss
        print(
            f"Read miss: Процессор {self.id} не имеет линии с тегом {bin(address//2)} у себя в кэше")
        data, state = self.read_in_others(address)
        # only in main memory
        if data is None:
            data = self.main_memory.data[address]
        # put data in cache
        self.change_time_n_save_state(40)
        self.rewrite_cacheline(address, data, state)
        if len(commands_amount) == 0 or self.id == commands_amount[-1]:
            self.change_time_n_save_state(20)
        return data

    def write(self, address):
        print('Логи:')
        line = self.cache.get_line(address)
        global time, commands_amount
        if len(commands_amount) == 0 or self.id == commands_amount[0]:
            self.change_time_n_save_state(20)
        if line is not None:
            # write hit
            print(
                f'Write hit:Процессор {self.id} имел линию {self.cache.lines.index(line)} с тэгом {bin(address//2)} и состоянием {states[line.state]}')
            data_0 = line.data
            line.data = (line.data + 1) % (2 ** CACHE_LINE_SIZE)
            print(
                f"Процессор {self.id} инкрементирует данные с тегом {bin(address//2)}: {data_0}=>{line.data} (состояние: {states[line.state]}=>{states[MODIFIED]})")
            if line.state != EXCLUSIVE and line.state != MODIFIED:
                self.invalidate_others(address)
            line.state = MODIFIED
            return line.data

        # Промах в кэше
        print(
            f"Write miss: Процессор {self.id} не имеет линии с тегом {bin(address//2)} у себя в кэше")
        data, state = self.RWITM_in_others(address)
        where = True
        if data is None:
            where = False
            data = self.main_memory.data[address]
            print(
                f"Процессор {self.id} читает данные {data} с тегом {bin(address//2)} из основной памяти")
        self.change_time_n_save_state(20)
        result_data = (data + 1) % (2 ** CACHE_LINE_SIZE)
        print(
            f"Процессор {self.id} инкрементирует данные с тегом {bin(address//2)}: {data}=>{result_data}")
        self.rewrite_cacheline(address, result_data, MODIFIED)
        if where:
            self.invalidate_others(address)
        return data + 1


# Функция инициализации системы
def initialize_system():
    global processors, memory, time, commands_amount, system_states, bus
    memory = MainMemory()
    time = 0
    bus = 0
    processors = [Processor(i, Cache(), memory) for i in range(NUM_PROCESSORS)]
    system_states[0] = get_system_state()


def user_interface():
    global processors, memory, time, commands_amount, bus
    many = False
    commands_amount = []

    while True:
        if many:
            if len(commands) > 0:
                print('Можете продолжать ввод команд')
                print('список команд на данный момент:')
                for i, command in enumerate(commands):
                    print(f'{command} {processor_ids[i]} {addresses[i]}')
            print("m - закончить ввод нескольких команд")
        else:
            print("Команды:")
            print("r <processor_id> <address> - чтение по адресу")
            print("w <processor_id> <address>  - запись по адресу")
            print("m - начать ввод нескольких команд")
            print("t - просмотреть состояние системы в при определенных tick")
            print("reset - сброс системы")
            print("exit - выход")

        command = input("Введите команду: ").split()

        if (command[0] == "r" or command[0] == "w") and len(command) < 3:
            print(
                f"Вы ввели не все необходимые данные\n")
            continue

        if (command[0] == "r" or command[0] == "w") and len(command) > 3:
            print(
                f"Вы ввели слишком много переменных\n")
            continue

        if (command[0] == "m") and len(command) != 1:
            print(
                f"Вы ввели слишком много переменных\n")
            continue

        if command[0] == "r" or command[0] == "w":
            try:
                number1 = int(command[1])
                number2 = int(command[2])
            except ValueError:
                print(
                    f"Введён неверный номер процессора или адрес. Их значение должно быть целочисленным\n")
                continue

            if int(command[1]) > 3 or int(command[1]) < 0:
                print(
                    f"Введён неверный номер процессора. Его значение должно быть от 0 до 3\n")
                continue
            if int(command[2]) > 15 or int(command[2]) < 0:
                print(
                    f"Введён неверный адрес. Его значение должно быть от 0 до 15\n")
                continue

        if command[0] == "r":
            processor_id = int(command[1])
            address = int(command[2])
            if not many:
                data = processors[processor_id].read(address)
                print(
                    f"Процессор {processor_id} успешно прочел данные {data} из адреса {bin(address)}\n")
                print_system_state()
            else:
                if processor_id in processor_ids:
                    ans = input(
                        'Команда данному процессору уже была отдана, переписать? y/N:')
                    if ans == 'y' or ans == 'Y':
                        i = processor_ids.index(processor_id)
                        commands[i] = 'r'
                        addresses[i] = address
                else:
                    commands.append('r')
                    processor_ids.append(processor_id)
                    commands_amount.append(processor_id)
                    addresses.append(address)


        elif command[0] == "w":
            processor_id = int(command[1])
            address = int(command[2])
            if not many:
                data = processors[processor_id].write(address)
                print(
                    f"Процессор {processor_id} успешно записал данные {data} в адрес {bin(address)}\n")
                print_system_state()
            else:
                if processor_id in processor_ids:
                    ans = input(
                        'Команда данному процессору уже была отдана, переписать? y/N:')
                    if ans == 'y' or ans == 'Y':
                        i = processor_ids.index(processor_id)
                        commands[i] = 'w'
                        addresses[i] = address
                else:
                    commands.append('w')
                    processor_ids.append(processor_id)
                    commands_amount.append(processor_id)
                    addresses.append(address)


        elif command[0] == "m":
            many = not many
            if many:
                commands = []
                processor_ids = []
                commands_amount = []
                addresses = []
                print(
                    f"Вводите команды - по одной на процессор")
            else:
                print("Выполнение команд")
                for i, command in enumerate(commands):
                    print(
                        f'Команда {i}: {command} {processor_ids[i]} {addresses[i]}')
                    if command == 'r':
                        global time

                        data = processors[processor_ids[i]].read(addresses[i])
                        data = processors[processor_ids[i]].read(addresses[i])
                        print(
                            f"Процессор {processor_id} успешно прочел данные {data} из адреса {bin(address)}\n")
                        print_system_state()
                    else:

                        data = processors[processor_ids[i]].write(addresses[i])
                        print(
                            f"Процессор {processor_ids[i]} успешно записал данные {data} в адрес {bin(addresses[i])}\n")
                        print_system_state()


        elif command[0] == "t":
            global system_states
            while True:
                print('\nВведите t чтобы продолжить вводить другие команды')
                keys = list(system_states.keys())
                key = input(
                    f'Введите значение tick от 0 до {keys[-1]}, чтобы увидеть состояние системы на тот момент времени (\'t\' - выход):')
                if key == 't':
                    break
                try:
                    destination_tick = int(key)
                except ValueError:
                    print(
                        f"Введён неверное значение тика. Их значение должно быть целочисленным\n")
                    continue
                if destination_tick < 0:
                    print(f'Значение должно быть больше 0')
                for i, tick in enumerate(keys):
                    if destination_tick >= tick:
                        print(system_states[tick])



        elif command[0] == "reset":
            initialize_system()
            many = False
            print("Система сброшена")

        elif command[0] == "exit":
            break

        else:
            print("Неизвестная команда")


# Функция вывода состояния системы
def print_system_state():
    global processors, memory, time, commands_amount, bus
    print(get_system_state())


def get_system_state():
    output = ''
    global processors, memory, time, commands_amount, bus
    output += "Состояние системы:\n"
    output += f"tick: {time}\n"
    output += f"Счётчик тактов доступа к шине: {bus}\n"
    output += "Основная память:\n"
    mem = PrettyTable(list(range(MEM_SIZE)))
    mem.add_row(tuple(memory.data))
    output += mem.get_string()
    output += "\nКэши процессоров:\n"
    headers = tuple(f"Процессор {i}" for i in range(NUM_PROCESSORS))
    x = PrettyTable(headers)
    for line_id in range(CACHE_SETS):
        row = tuple()
        for i in range(NUM_PROCESSORS):
            line = processors[i].cache.lines[line_id]
            row += (
                f"Строка {line_id}: tag={bin(line.tag//2)}, data={line.data}, state={states[line.state]};",)
        x.add_row(row)
    output += x.get_string()
    return output


# Инициализация и запуск системы
initialize_system()
print_system_state()
user_interface()
