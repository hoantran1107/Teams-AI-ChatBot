from pathlib import Path

# Get the absolute path using pathlib
absolute_path = Path(__file__).parent


def project_path() -> str:
    """Returns the absolute path of the project."""
    return str(absolute_path.parent.parent)


def data_path(*sub_folders: str) -> str:
    """Returns the absolute path to the data directory, optionally appending any subfolders provided.

    Example:
        >>> data_path()
        '/absolute/path/to/project/data'
        >>> data_path('subfolder1', 'subfolder2')
        '/absolute/path/to/project/data/subfolder1/subfolder2'

    """
    path = Path(project_path()) / "data"
    for folder in sub_folders:
        path = path / folder
    return str(path)


def confluence_path(*sub_folders: str) -> str:
    """Returns the absolute path to the confluence directory, optionally appending any subfolders provided.

    Example:
        >>> confluence_path()
        '/absolute/path/to/project/confluence'
        >>> confluence_path('subfolder1', 'subfolder2')
        '/absolute/path/to/project/confluence/subfolder1/subfolder2'

    """
    path = Path(project_path()) / "confluence"
    for folder in sub_folders:
        path = path / folder
    return str(path)


def get_sqldb_path(*sub_folders: str) -> str:
    """Returns the relative path to the 'sqldb' directory, optionally appending any subfolders provided.

    Example:
        >>> get_sqldb_path()
        'relative/path/to/sqldb'
        >>> get_sqldb_path('subfolder1', 'subfolder2')
        'relative/path/to/sqldb/subfolder1/subfolder2'

    """
    path = Path(project_path()) / "sqldb"
    for folder in sub_folders:
        path = path / folder
    return str(path.relative_to(Path.cwd()))


def get_local_store_path(*sub_folders: str) -> str:
    """Returns the relative path to the 'local_store' directory, optionally appending any subfolders provided.

    Example:
        >>> get_local_store_path()
        'relative/path/to/local_store'
        >>> get_local_store_path('subfolder1', 'subfolder2')
        'relative/path/to/local_store/subfolder1/subfolder2'

    """
    path = Path(project_path()) / "local_store"
    for folder in sub_folders:
        path = path / folder
    return str(path.relative_to(Path.cwd()))


def concat_path(original_path: str, *args: str) -> str:
    """Concatenates the given path with additional path components.

    Examples:
        >>> concat_path('/path/to/dir', 'subdir', 'file.txt')
        '/path/to/dir/subdir/file.txt'
        >>> concat_path('/path/to/dir', 'subdir')
        '/path/to/dir/subdir'

    """
    path = Path(original_path)
    for arg in args:
        path = path / arg
    return str(path)


if __name__ == "__main__":
    print(list(Path(project_path()).iterdir()))
    print(get_sqldb_path())
