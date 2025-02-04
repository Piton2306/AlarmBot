import os


def print_directory_structure(start_path, output_file, exclude_dirs=None, exclude_files=None, include_files=None):
    """
    Рекурсивно выводит структуру папки и вложенных файлов, исключая указанные папки и файлы,
    и записывает содержимое файлов в отдельный файл.

    :param start_path: Путь к начальной директории.
    :param output_file: Путь к файлу, в который будет записано содержимое.
    :param exclude_dirs: Список папок, которые нужно исключить.
    :param exclude_files: Список файлов, которые нужно исключить.
    :param include_files: Список файлов, которые нужно включить, даже если они находятся в исключенных папках.
    """
    if exclude_dirs is None:
        exclude_dirs = []
    if exclude_files is None:
        exclude_files = []
    if include_files is None:
        include_files = []

    with open(output_file, 'w', encoding='utf-8') as f_out:
        # Выводим имя проекта
        project_name = os.path.basename(os.path.abspath(start_path))
        f_out.write(f"Проект: {project_name}\n\n")

        # Выводим структуру папки
        f_out.write("Структура папки:\n")
        for root, dirs, files in os.walk(start_path):
            # Исключаем папки
            dirs[:] = [d for d in dirs if d not in exclude_dirs]

            level = root.replace(start_path, '').count(os.sep)
            indent = ' ' * 4 * (level)
            if level == 0:
                f_out.write(f"{os.path.basename(root)}/\n")
            else:
                relative_path = os.path.relpath(root, start_path)
                f_out.write(f"{indent}{relative_path}/\n")
            sub_indent = ' ' * 4 * (level + 1)

            # Исключаем файлы
            for file in files:
                if not any(file.endswith(ext) for ext in exclude_files) or any(
                        file.endswith(ext) for ext in include_files):
                    f_out.write(f"{sub_indent}{file}\n")

        f_out.write("\nСодержимое файлов:\n")

        # Выводим содержимое файлов
        for root, dirs, files in os.walk(start_path):
            # Исключаем папки
            dirs[:] = [d for d in dirs if d not in exclude_dirs]

            # Исключаем файлы
            for file in files:
                if not any(file.endswith(ext) for ext in exclude_files) or any(
                        file.endswith(ext) for ext in include_files):
                    file_path = os.path.join(root, file)
                    if isinstance(start_path, str) and isinstance(file_path, str):
                        relative_path = os.path.relpath(file_path, start_path)
                        f_out.write("---------------\n")
                        f_out.write(f"{relative_path}\n\n")
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f_in:
                                content = f_in.read()
                                f_out.write(f"{content}\n\n")
                        except Exception as e:
                            f_out.write(f"Ошибка чтения файла: {e}\n\n")
                    else:
                        f_out.write(f"Ошибка: Неправильный тип пути для файла {file_path}\n\n")


# Пример использования
if __name__ == "__main__":
    start_path = "."  # Начальная директория (текущая директория)
    output_file = "directory_structure.txt"  # Файл, в который будет записано содержимое
    exclude_dirs = ["logs",".pytest_cache",".venv", ".git", ".idea", "__pycache__", "file", "venv"]  # Папки, которые нужно исключить
    exclude_files = ["test_reminder_bot.py","run_bot.bat","env",".tmp", ".gitignore", "database_parser_dollars.db", "directory_structure.txt", "tess.py",
                     "requirements.txt", ".log", "print_directory_structure.py","reminders.db",
                     "init.py"]  # Файлы, которые нужно исключить
    include_files = []  # Файлы, которые нужно включить, даже если они находятся в исключенных папках
    print_directory_structure(start_path, output_file, exclude_dirs=exclude_dirs, exclude_files=exclude_files,
                              include_files=include_files)
