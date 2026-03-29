# Workflow para Extração de Funções de Arquivos .so Stripados

Este repositório contém um workflow e um script Python para extrair endereços e nomes de funções (originais e *demangled*) de arquivos `.so` (shared object) que foram *stripados*.

## Contexto

Arquivos `.so` *stripados* têm suas tabelas de símbolos removidas ou minimizadas, dificultando a engenharia reversa. No entanto, símbolos dinâmicos e algumas informações ainda podem estar presentes, permitindo a recuperação de nomes de funções, especialmente aquelas exportadas ou referenciadas externamente. Este workflow utiliza ferramentas padrão do Linux (`readelf` e `c++filt`) para realizar essa extração.

## Estrutura do Repositório

- `files/`: Contém os arquivos `.so` de exemplo (`libfs14.so`, `libfs16.so`, `libfs18.so`).
- `extract_functions.py`: Script Python para automatizar a extração de funções.
- `output/`: Diretório onde os resultados da extração serão salvos.
- `README.md`: Este arquivo de documentação.

## Ferramentas Utilizadas

- **`readelf`**: Uma ferramenta do GNU Binutils para exibir informações sobre arquivos ELF (Executable and Linkable Format). Usamos `readelf -Ws` para listar os símbolos dinâmicos, que muitas vezes contêm nomes de funções mesmo em binários *stripados*.
- **`c++filt`**: Uma ferramenta para *demangle* nomes de símbolos C++. Nomes de funções C++ são frequentemente *mangled* (decorados) pelo compilador para incluir informações sobre seus tipos de parâmetros e namespaces. `c++filt` converte esses nomes de volta para uma forma legível.

## Como Usar o Workflow

### Pré-requisitos

Certifique-se de ter as seguintes ferramentas instaladas em seu sistema:

- `python3`
- `binutils` (que inclui `readelf`)
- `c++filt` (geralmente parte do `binutils` ou `g++`)

No ambiente de sandbox, `binutils` foi instalado via `sudo apt-get install -y binutils`.

### Execução

1.  **Clone o repositório** (se ainda não o fez):
    ```bash
    gh repo clone snowbit64/reverse-engineering /home/ubuntu/reverse-engineering
    cd /home/ubuntu/reverse-engineering
    ```

2.  **Execute o script Python**:
    ```bash
    python3 extract_functions.py
    ```

    O script irá processar todos os arquivos `.so` encontrados no diretório `files/` e salvar os resultados no diretório `output/`.

## Saída

Para cada arquivo `.so` processado, um arquivo de texto será gerado no diretório `output/` com o formato `[nome_do_arquivo].so_functions.txt`. Este arquivo conterá uma lista de funções encontradas, com as seguintes colunas:

- **Endereço**: O endereço de memória da função no binário.
- **Nome Original**: O nome do símbolo como encontrado pelo `readelf` (pode ser *mangled*).
- **Nome Demangled**: O nome da função após o processamento por `c++filt`, tornando-o mais legível (aplicável principalmente a funções C++).

Exemplo de saída (trecho):

```
# Funções extraídas de libfs14.so
# Endereço           | Nome Original                            | Nome Demangled
----------------------------------------------------------------------------------------------------
000000000013661c   | _ZN19ServerListBackplateD1Ev             | ServerListBackplate::~ServerListBackplate()
0000000000129d3c   | _ZN12OptionButtonC2Ej9eOptionIDiiii16eScreenAlignment17eElementAlignment | OptionButton::OptionButton(unsigned int, eOptionID, int, int, int, int, eScreenAlignment, eElementAlignment)
...
```

## O Script `extract_functions.py`

```python
import subprocess
import os
import re

def extract_functions(so_path):
    print(f"Processando: {so_path}")
    
    # Usar readelf -Ws para listar todos os símbolos, incluindo dinâmicos
    # -W evita truncamento de nomes longos
    try:
        result = subprocess.run([\"readelf\", \"-Ws\", so_path], capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Erro ao executar readelf em {so_path}: {e}")
        return []

    functions = []
    # Regex para capturar: Valor (Endereço), Tamanho, Tipo, Visibilidade, Índice da Seção, Nome
    # Exemplo: 3238: 000000000022f564   444 FUNC    GLOBAL DEFAULT   10 ov_bitrate
    pattern = re.compile(r\"^\\s*\\d+:\\s+([0-9a-fA-F]+)\\s+\\d+\\s+FUNC\\s+\\w+\\s+\\w+\\s+\\d+\\s+(.+)$\")

    for line in result.stdout.splitlines():
        match = pattern.match(line)
        if match:
            addr = match.group(1)
            name = match.group(2)
            functions.append((addr, name))

    return functions

def demangle_names(names):
    if not names:
        return {}
    
    # Usar c++filt para fazer o demangle de nomes C++ (mangled)
    try:
        # Enviar todos os nomes de uma vez para o stdin do c++filt para performance
        process = subprocess.Popen([\"c++filt\"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        stdout, _ = process.communicate(input=\"\\n\".join(names))
        demangled = stdout.splitlines()
        return dict(zip(names, demangled))
    except Exception as e:
        print(f\"Erro ao executar c++filt: {e}\")
        return {name: name for name in names}

def main():
    files_dir = \"/home/ubuntu/reverse-engineering/files\"
    output_dir = \"/home/ubuntu/reverse-engineering/output\"
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for filename in os.listdir(files_dir):
        if filename.endswith(\".so\"):
            so_path = os.path.join(files_dir, filename)
            functions = extract_functions(so_path)
            
            if functions:
                names = [f[1] for f in functions]
                demangled_map = demangle_names(names)
                
                output_path = os.path.join(output_dir, f\"{filename}_functions.txt\")
                with open(output_path, \"w\") as f:
                    f.write(f\"# Funções extraídas de {filename}\\n\")
                    f.write(f\"# {\"Endereço\":<18} | {\"Nome Original\":<40} | {\"Nome Demangled\"}\\n\")
                    f.write(\"-\" * 100 + \"\\n\")
                    for addr, name in functions:
                        d_name = demangled_map.get(name, name)
                        f.write(f\"{addr:<18} | {name:<40} | {d_name}\\n\")
                
                print(f\"Sucesso! {len(functions)} funções salvas em {output_path}\")
            else:
                print(f\"Nenhuma função encontrada com símbolos dinâmicos em {filename}\")

if __name__ == \"__main__\":
    main()
```

## Limitações

Este método se baseia na presença de símbolos dinâmicos. Para binários *completamente stripados* (onde até mesmo os símbolos dinâmicos foram removidos), a recuperação de nomes de funções é significativamente mais difícil e exigiria técnicas avançadas de engenharia reversa, como análise de assinaturas de funções, análise de fluxo de controle e inferência de tipos, geralmente realizadas com ferramentas como Ghidra, IDA Pro ou radare2.
