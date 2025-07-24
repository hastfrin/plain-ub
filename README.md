## PLAIN UB

![Imagem de Cabeçalho](assets/dark.png#gh-dark-mode-only)
![Imagem de Cabeçalho](assets/light.png#gh-light-mode-only)

Um User-Bot simples para o Telegram.

> Feito para meu uso pessoal

## Exemplos de Plugins:

<details>

<summary></summary>
 
* Plugin Básico:
```python
from app import BOT, bot, Message

@bot.add_cmd(cmd="test")
async def test_function(bot: BOT, message: Message):
    await message.reply("Testando....")
    """O restante do seu código."""
    
```

* Plugin com Múltiplos Comandos:    
Em vez de empilhar @add_cmd, você pode passar uma lista de comandos.
```python
from app import BOT, bot, Message

@bot.add_cmd(cmd=["cmd1", "cmd2"])
async def test_function(bot: BOT, message: Message):
    if message.cmd=="cmd1":
        await message.reply("Função acionada pelo cmd1")
    """O restante do seu código."""
    
```

* Plugin com acesso ao Banco de Dados:

```python
from app import BOT, bot, Message, CustomDB

TEST_COLLECTION = CustomDB["TEST_COLLECTION"]

@bot.add_cmd(cmd="add_data")
async def test_function(bot: BOT, message: Message):
    async for data in TEST_COLLECTION.find():
        """O restante do seu código."""
    # OU
    await TEST_COLLECTION.add_data(data={"_id":"teste", "data":"algum_dado"})
    await TEST_COLLECTION.delete_data(id="teste")
```

* Plugin Conversacional:
    * Método Vinculado
        ```python
        from pyrogram import filters
        from app import BOT, bot, Message
        @bot.add_cmd(cmd="test")
        async def test_function(bot: BOT, message: Message):
            response = await message.get_response(
                filters=filters.text&filters.user([1234]), 
                timeout=10,
            )
            # Retorna o primeiro texto recebido no chat onde o comando foi executado
            """O restante do seu código"""
               
        ```
    * Conversacional
        
        ```python
        from app import BOT, bot, Message, Convo
        from pyrogram import filters
      
        @bot.add_cmd(cmd="test")
        async def test_function(bot: BOT, message: Message):
            async with Convo(
                client=bot, 
                chat_id=1234, 
                filters=filters.text, 
                timeout=10
            ) as convo:
                await convo.get_response(timeout=10)
                await convo.send_message(text="abc", get_response=True, timeout=8)
                # e assim por diante
            
        ```
</details>
