from setuptools import setup, find_packages

# Read the contents of your README file
with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

setup(
    name="enterprise-umbrella-reminder",
    version="2.0.0",
    packages=find_packages(),
    
    install_requires=[
        "requests>=2.25.0",
        "beautifulsoup4>=4.9.3",
        "geopy>=2.1.0",
        "configparser>=5.0.2",
    ],
    
    entry_points={
        "console_scripts": [
            "umbrella-reminder=umbrella_reminder.cli:main",
        ],
    },
    
    author="AI Assistant",
    author_email="assistant@example.com",
    description="An enterprise-grade, modular command-line tool to check for rain.",
    long_description=long_description,
    long_description_content_type='text/markdown',
    url="<your-repo-url-here>",
    
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Utilities",
    ],
    python_requires='>=3.6',
) 