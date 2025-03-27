# Contributing to Scrapy

Thank you for considering contributing to Scrapy! This document outlines the process for contributing to the project.

## Code of Conduct

By participating in this project, you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md).

## How Can I Contribute?

### Reporting Bugs

- Check if the bug has already been reported in the [Issues](https://github.com/yourusername/scrapy/issues) section.
- If not, create a new issue with a clear title and description.
- Include steps to reproduce the bug, expected behavior, and actual behavior.
- If possible, include screenshots or code samples.

### Suggesting Enhancements

- Check if the enhancement has already been suggested in the [Issues](https://github.com/yourusername/scrapy/issues) section.
- If not, create a new issue with a clear title and description.
- Explain why the enhancement would be useful to most Scrapy users.
- Include any relevant examples or mock-ups.

### Your First Code Contribution

1. Fork the repository.
2. Clone your fork locally:
   ```bash
   git clone https://github.com/yourusername/scrapy.git
   cd scrapy
   ```
3. Create a new branch for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```
4. Make your changes.
5. Run tests to ensure your changes don't break existing functionality:
   ```bash
   pytest tests/
   ```
6. Push your changes to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```
7. Create a pull request from your fork to the main repository.

### Pull Requests

1. Update the documentation to reflect any changes.
2. Update the README.md if necessary.
3. Include tests for new functionality.
4. Ensure all tests pass.
5. Keep your pull request focused on a single topic.

## Development Guidelines

### Code Style

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) for Python code.
- Use meaningful variable and function names.
- Include type hints where appropriate.
- Document all functions, classes, and modules using docstrings.

### Testing

- Write tests for all new functionality.
- Ensure all tests pass before submitting a pull request.
- Tests should be placed in the `tests/` directory.

### Documentation

- Update documentation to reflect any changes.
- Use clear, concise language.
- Include examples where appropriate.
- Documentation should be placed in the `docs/` directory.

## Setting Up Your Development Environment

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```

3. Install the package in development mode:
   ```bash
   pip install -e .
   ```

## Project Structure

```
scrapy/
├── api/                  # API server code
├── cli/                  # Command-line interface code
├── clients/              # Client libraries for different languages
├── docs/                 # Documentation
├── examples/             # Example scripts and projects
├── scraping_project/     # Core scraping code
│   ├── distributed/      # Distributed scraping functionality
│   └── ...
├── tests/                # Test suite
├── visualization/        # Data visualization code
└── ...
```

## Commit Message Guidelines

- Use the present tense ("Add feature" not "Added feature").
- Use the imperative mood ("Move cursor to..." not "Moves cursor to...").
- Limit the first line to 72 characters or less.
- Reference issues and pull requests liberally after the first line.

## Releasing

Project maintainers are responsible for releasing new versions. The release process is as follows:

1. Update the version number in `setup.py` and `__init__.py`.
2. Update the changelog.
3. Create a new release on GitHub.

## Getting Help

If you have questions or need help, you can:

- [Open an issue](https://github.com/yourusername/scrapy/issues)
- Reach out to the maintainers directly

Thank you for contributing to Scrapy!
