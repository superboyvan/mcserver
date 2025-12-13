const mineflayer = require('mineflayer');
const { pathfinder, Movements, goals } = require('mineflayer-pathfinder');
const { GoalNear, GoalBlock } = goals;
const Vec3 = require('vec3');

let bot;
let targetBlockName = 'log';
let minedCount = 0;
let savedChestPos = null;
let totalMined = 0;
let isActive = true;
let autoEat = true;
let minHealth = 2; // Lower default so it keeps working
let autoReplant = false;

function startBot() {
  bot = mineflayer.createBot({
    host: '192.168.110.210',
    port: 25565,
    username: 'TreeDudeBot'
  });

  bot.loadPlugin(pathfinder);

  bot.once('spawn', () => {
    console.log('🤖 Bot spawned and ready!');
    const mcData = require('minecraft-data')(bot.version);
    const movements = new Movements(bot, mcData);
    
    // Allow breaking and placing blocks to navigate
    movements.canDig = true;
    movements.allow1by1towers = true;
    movements.allowFreeMotion = true;
    movements.allowParkour = true;
    movements.allowSprinting = true;
    
    // Set scaffold item (will use dirt/cobblestone from inventory)
    movements.scaffoldingBlocks = [];
    const scaffoldItems = bot.inventory.items().filter(i => 
      i.name.includes('dirt') || 
      i.name.includes('cobblestone') || 
      i.name.includes('stone') ||
      i.name.includes('netherrack')
    );
    scaffoldItems.forEach(item => movements.scaffoldingBlocks.push(item.type));
    
    bot.pathfinder.setMovements(movements);
    console.log('✅ Pathfinder loaded with digging & building enabled');
    displayStats();
    console.log('✅ Stats display started');
    console.log('🚀 Starting main loop...');
    startLoop();
    
    // Auto-eat checker
    setInterval(() => {
      if (bot.food < 18 || bot.health < 15) {
        autoEatFood().catch(err => console.log('Auto-eat failed:', err.message));
      }
    }, 5000);
    console.log('✅ Auto-eat monitor started');
  });

  bot.on('chat', (username, message) => {
    handleCommands(username, message).catch(err => console.log('Command error:', err.message));
  });
  
  bot.on('entityHurt', handleCombat);
  
  bot.on('end', () => {
    console.log('⚠️ Disconnected, reconnecting in 5s...');
    setTimeout(startBot, 5000);
  });
  bot.on('error', err => console.log('❌ Error:', err.message));
}

async function handleCommands(username, message) {
  if (!message.startsWith('?')) return;
  
  const args = message.slice(1).trim().toLowerCase().split(' ');
  const cmd = args[0];

  switch(cmd) {
    case 'target':
      targetBlockName = args[1] || 'log';
      minedCount = 0;
      bot.chat(`🎯 Target: ${targetBlockName}`);
      break;
    case 'pause':
      isActive = false;
      bot.chat('⏸️ Paused');
      break;
    case 'resume':
      isActive = true;
      bot.chat('▶️ Resumed');
      break;
    case 'stats':
      bot.chat(`📊 Mined: ${totalMined} | Inventory: ${minedCount}/64`);
      break;
    case 'replant':
      autoReplant = !autoReplant;
      bot.chat(`🌱 Auto-replant: ${autoReplant ? 'ON' : 'OFF'}`);
      break;
    case 'come':
      const player = bot.players[username];
      if (player) {
        bot.pathfinder.setGoal(new GoalNear(player.entity.position.x, player.entity.position.y, player.entity.position.z, 2));
        bot.chat('🏃 Coming!');
      }
      break;
    case 'chest':
      savedChestPos = null;
      bot.chat('📦 Chest reset');
      break;
    case 'feed':
      await autoEatFood();
      bot.chat(`🍖 Food: ${bot.food}/20 | HP: ${bot.health}/20`);
      break;
    case 'yolo':
      minHealth = 1;
      bot.chat('💀 YOLO MODE - ignoring health!');
      break;
    case 'inv':
      console.log('📦 Inventory:');
      bot.inventory.items().forEach(i => console.log(`  - ${i.name} x${i.count}`));
      bot.chat('Check console for inventory');
      break;
    case 'dropoff':
    case 'deposit':
      bot.chat('🔍 Searching for nearest chest...');
      await findAndConfirmChest();
      break;
    case 'help':
      bot.chat('Commands: ?target ?pause ?resume ?stats ?replant ?come ?chest ?feed ?yolo ?inv ?dropoff');
      break;
  }
}

function handleCombat(entity) {
  if (entity === bot.entity) return;
  if (entity.position && bot.entity.position.distanceTo(entity.position) < 5) {
    console.log('⚔️ Fighting back!');
    bot.attack(entity);
    setTimeout(() => bot.attack(entity), 500);
  }
}

async function autoEatFood() {
  console.log(`🍽️ Food check: HP ${bot.health}/20 | Hunger ${bot.food}/20`);
  
  // List ALL items to debug
  console.log('Current inventory:', bot.inventory.items().map(i => i.name).join(', '));
  
  const food = bot.inventory.items().find(item => {
    const name = item.name.toLowerCase();
    return name.includes('steak') ||
           name.includes('bread') || 
           name.includes('cooked') ||
           name.includes('apple') ||
           name.includes('golden') ||
           name.includes('carrot') ||
           name.includes('potato') ||
           name.includes('beef') ||
           name.includes('porkchop') ||
           name.includes('chicken') ||
           name.includes('mutton') ||
           name.includes('fish') ||
           name.includes('salmon') ||
           name.includes('cookie') ||
           name.includes('melon') ||
           name.includes('pumpkin_pie') ||
           name.includes('rabbit') ||
           name.includes('suspicious_stew');
  });

  if (food) {
    console.log(`🍖 Eating: ${food.name}`);
    try {
      await bot.equip(food, 'hand');
      bot.activateItem();
      await sleep(2000);
      console.log(`✅ Done eating!`);
    } catch (err) {
      console.log('❌ Eat error:', err.message);
    }
  } else {
    console.log('⚠️ NO EDIBLE FOOD FOUND');
  }
}

async function startLoop() {
  console.log('🔄 Main loop started! isActive:', isActive);
  while (true) {
    try {
      if (!isActive) {
        await sleep(1000);
        continue;
      }

      console.log(`🔍 Looking for ${targetBlockName}... HP: ${bot.health}/20 Food: ${bot.food}/20`);

      // Health check - just eat if possible and keep going
      if (bot.health < minHealth || bot.food < 6) {
        console.log(`⚠️ Low health/food (${bot.health}/20 HP, ${bot.food}/20 Food) - eating and continuing...`);
        await autoEatFood();
        await sleep(1000);
        // Don't continue the loop, just keep mining
      }

      const block = bot.findBlock({
        matching: b => b.name.includes(targetBlockName),
        maxDistance: 256 // Maximum possible render distance
      });

      if (!block) {
        console.log(`🔍 No ${targetBlockName} within 256 blocks, wandering...`);
        await wander();
        await sleep(2000);
        continue;
      }

      await equipBestTool(block);
      
      // Try to reach the block with retries
      let reached = false;
      for (let attempt = 1; attempt <= 20; attempt++) {
        try {
          // Update scaffolding blocks before each attempt
          updateScaffoldingBlocks();
          await bot.pathfinder.goto(new GoalNear(block.position.x, block.position.y, block.position.z, 1));
          reached = true;
          break;
        } catch (err) {
          if (attempt < 20) {
            console.log(`Pathfinding attempt ${attempt}/20 failed, retrying...`);
            
            // Try to clear path by breaking blocks in the way
            if (attempt % 5 === 0) {
              await clearPath(block.position);
            }
            
            await sleep(200);
          } else {
            console.log('Cannot reach block after 20 attempts, skipping...');
          }
        }
      }
      
      if (!reached) continue;
      
      const blockPos = block.position.clone();
      await bot.dig(block);
      
      console.log(`⛏️ Mined ${targetBlockName} | Total: ${++totalMined}`);
      minedCount++;

      // Auto-replant saplings
      if (autoReplant && targetBlockName.includes('log')) {
        await replantSapling(blockPos);
      }

      // Deposit when inventory full
      if (minedCount >= 64 || bot.inventory.items().length >= 35) {
        await depositToChest();
        minedCount = 0;
      }

      await sleep(500);

    } catch (err) {
      console.log('❌ Loop error:', err.message);
      await sleep(1000);
    }
  }
}

async function equipBestTool(block) {
  try {
    console.log(`🔧 Looking for tool to mine ${block.name}...`);
    
    const toolType = block.name.includes('log') || block.name.includes('wood') ? 'axe' : 
                     block.name.includes('stone') || block.name.includes('ore') || block.name.includes('cobblestone') ? 'pickaxe' :
                     block.name.includes('dirt') || block.name.includes('grass') || block.name.includes('sand') ? 'shovel' : null;

    if (!toolType) {
      console.log('No specific tool needed, using hands');
      return;
    }

    console.log(`Need: ${toolType}`);
    
    const tools = bot.inventory.items()
      .filter(i => i.name.includes(toolType))
      .sort((a,b) => {
        const materials = ['netherite', 'diamond', 'iron', 'stone', 'wooden', 'wood'];
        const aIndex = materials.findIndex(m => a.name.includes(m));
        const bIndex = materials.findIndex(m => b.name.includes(m));
        if (aIndex === -1) return 1;
        if (bIndex === -1) return -1;
        return aIndex - bIndex;
      });

    if (tools.length === 0) {
      console.log(`⚠️ No ${toolType} found! Mining with hands...`);
      bot.chat(`⚠️ I need a ${toolType}!`);
      return;
    }
    
    const bestTool = tools[0];
    console.log(`✅ Equipping ${bestTool.name}`);
    await bot.equip(bestTool, 'hand');
    console.log(`✅ ${bestTool.name} equipped!`);
    
  } catch (err) {
    console.log(`❌ Tool equip error: ${err.message}`);
  }
}

async function replantSapling(position) {
  try {
    const sapling = bot.inventory.items().find(i => i.name.includes('sapling'));
    if (!sapling) return;

    await bot.equip(sapling, 'hand');
    await bot.placeBlock(bot.blockAt(position.offset(0, -1, 0)), new Vec3(0, 1, 0));
    console.log('🌱 Replanted sapling');
  } catch (err) {
    // Silently fail if can't replant
  }
}

async function depositToChest() {
  try {
    console.log('🚚 Starting deposit sequence...');
    
    if (!savedChestPos) {
      console.log('❌ No chest location saved!');
      bot.chat('❌ No chest set! Use ?dropoff first.');
      return;
    }

    const chest = bot.blockAt(savedChestPos);
    if (!chest || !chest.name.includes('chest')) {
      console.log('⚠️ Saved chest not found!');
      bot.chat('⚠️ Chest missing! Use ?dropoff to set a new one.');
      savedChestPos = null;
      return;
    }

    console.log(`🎯 Going to saved chest at ${savedChestPos}...`);
    
    // Try multiple times with different approaches
    let arrived = false;
    for (let attempt = 1; attempt <= 20; attempt++) {
      try {
        console.log(`Attempt ${attempt}/20 to reach chest...`);
        updateScaffoldingBlocks();
        const distance = Math.min(1 + Math.floor(attempt / 5), 4); // Gradually increase distance
        await bot.pathfinder.goto(new GoalNear(chest.position.x, chest.position.y, chest.position.z, distance));
        arrived = true;
        console.log('✅ Arrived at chest!');
        break;
      } catch (err) {
        if (attempt < 20) {
          console.log(`Attempt ${attempt} failed: ${err.message}`);
          
          // Try to clear path every 5 attempts
          if (attempt % 5 === 0) {
            await clearPath(chest.position);
          }
          
          await sleep(300);
        }
      }
    }
    
    if (!arrived) {
      bot.chat('❌ Cannot reach chest after 20 attempts! Clear the path or use ?chest to reset.');
      return;
    }

    console.log('📦 Opening chest...');
    const chestObj = await bot.openChest(chest);
    
    // Deposit EVERYTHING except tools, weapons, armor, and food
    const items = bot.inventory.items().filter(i => {
      const name = i.name.toLowerCase();
      // Keep tools
      if (name.includes('axe') || name.includes('pickaxe') || name.includes('shovel') || name.includes('hoe')) return false;
      // Keep weapons
      if (name.includes('sword') || name.includes('bow') || name.includes('crossbow')) return false;
      // Keep armor
      if (name.includes('helmet') || name.includes('chestplate') || name.includes('leggings') || name.includes('boots')) return false;
      // Keep food
      if (name.includes('steak') || name.includes('bread') || name.includes('cooked') || 
          name.includes('apple') || name.includes('golden') || name.includes('carrot') || 
          name.includes('potato') || name.includes('beef') || name.includes('food')) return false;
      // Deposit everything else
      return true;
    });
    
    console.log(`📤 Depositing ${items.length} item types...`);
    for (const item of items) {
      try {
        await chestObj.deposit(item.type, null, item.count);
        console.log(`  ✓ ${item.count}x ${item.name}`);
      } catch (e) {
        console.log(`  ✗ Failed to deposit ${item.name}: ${e.message}`);
      }
    }
    chestObj.close();
    console.log('✅ Deposit complete!');
    bot.chat(`💰 Deposited! Total mined: ${totalMined}`);
  } catch (err) {
    console.log('❌ Deposit error:', err.message);
    bot.chat(`❌ Deposit failed: ${err.message}`);
  }
}

async function findAndConfirmChest() {
  try {
    console.log('🔍 Searching for chest within 256 blocks...');
    
    const chest = bot.findBlock({
      matching: b => b.name.includes('chest') || b.name.includes('barrel'),
      maxDistance: 256
    });

    if (!chest) {
      console.log('❌ No chest found within 256 blocks!');
      bot.chat('❌ No chest found nearby!');
      return;
    }

    console.log(`✅ Found chest at ${chest.position}`);
    bot.chat(`Found chest at ${Math.floor(chest.position.x)}, ${Math.floor(chest.position.y)}, ${Math.floor(chest.position.z)}`);
    
    console.log('🚶 Going to chest...');
    
    // Try multiple times to reach the chest
    let arrived = false;
    for (let attempt = 1; attempt <= 20; attempt++) {
      try {
        console.log(`Pathfinding attempt ${attempt}/20...`);
        updateScaffoldingBlocks();
        const distance = Math.min(2 + Math.floor(attempt / 5), 5);
        await bot.pathfinder.goto(new GoalNear(chest.position.x, chest.position.y, chest.position.z, distance));
        arrived = true;
        console.log('✅ Arrived!');
        break;
      } catch (err) {
        if (attempt < 20) {
          console.log(`Attempt ${attempt} failed: ${err.message}`);
          
          // Try to clear path every 5 attempts
          if (attempt % 5 === 0) {
            await clearPath(chest.position);
          }
          
          await sleep(300);
        }
      }
    }
    
    if (!arrived) {
      bot.chat('❌ Cannot reach that chest after 20 attempts! Find one closer or clear the path.');
      return;
    }
    
    // Auto-save and use this chest
    savedChestPos = chest.position;
    console.log('✅ Chest auto-saved!');
    bot.chat('✅ Using this chest! Depositing now...');
    
    await depositToChest();
    minedCount = 0;
    
  } catch (err) {
    console.log('❌ Error finding chest:', err.message);
    bot.chat(`❌ Error: ${err.message}`);
  }
}

async function waitForChestOpen() {
  return new Promise((resolve) => {
    console.log('👀 Watching for chest to open...');
    
    const timeout = setTimeout(() => {
      bot.removeListener('windowOpen', onWindowOpen);
      bot.chat('⏰ Timed out waiting for chest');
      console.log('❌ Timeout - no chest opened in 30 seconds');
      resolve();
    }, 30000);

    function onWindowOpen(window) {
      console.log(`🪟 Window opened! Type: ${window.type}`);
      
      if (window.type === 'minecraft:chest' || window.type === 'minecraft:barrel' || 
          window.type === 'minecraft:generic_9x3' || window.type.includes('chest')) {
        clearTimeout(timeout);
        bot.removeListener('windowOpen', onWindowOpen);
        
        console.log('✅ Chest window detected! Finding chest block...');
        
        // Get the chest position from nearby blocks
        const chest = bot.findBlock({
          matching: b => {
            const isChest = b.name.includes('chest') || b.name.includes('barrel');
            const distance = bot.entity.position.distanceTo(b.position);
            console.log(`  Checking ${b.name} at distance ${distance.toFixed(2)}`);
            return isChest && distance < 6;
          },
          maxDistance: 6
        });
        
        if (chest) {
          savedChestPos = chest.position;
          console.log(`✅ Chest saved at ${savedChestPos}!`);
          bot.chat(`✅ Chest locked in at ${Math.floor(chest.position.x)}, ${Math.floor(chest.position.y)}, ${Math.floor(chest.position.z)}`);
          
          // Close the window first
          bot.closeWindow(window);
          
          // Now go deposit
          setTimeout(async () => {
            console.log('🚚 Starting auto-deposit...');
            await depositToChest();
            minedCount = 0;
          }, 1000);
        } else {
          bot.chat('❌ Could not find the chest you opened');
          console.log('❌ Failed to locate chest block nearby');
        }
        
        resolve();
      }
    }
    
    bot.on('windowOpen', onWindowOpen);
    console.log('✅ Listener registered, waiting for you to open a chest...');
  });
}

async function wander() {
  const x = bot.entity.position.x + (Math.random() * 80 - 40); // Wander farther
  const z = bot.entity.position.z + (Math.random() * 80 - 40);
  const y = bot.entity.position.y;
  
  console.log(`🚶 Wandering to ${Math.floor(x)}, ${Math.floor(y)}, ${Math.floor(z)}...`);
  
  try {
    await bot.pathfinder.goto(new GoalNear(x, y, z, 3), 10000); // More time to travel
  } catch (err) {
    console.log('Wander interrupted, searching new area...');
  }
}

function waitForResponse(validResponses, timeout = 30000) {
  return new Promise(resolve => {
    const timer = setTimeout(() => {
      bot.removeListener('chat', onChat);
      resolve(null);
    }, timeout);

    function onChat(username, message) {
      const msg = message.toLowerCase();
      if (validResponses.includes(msg)) {
        clearTimeout(timer);
        bot.removeListener('chat', onChat);
        resolve(msg);
      }
    }
    bot.on('chat', onChat);
  });
}

function displayStats() {
  setInterval(() => {
    if (isActive) {
      console.log(`📊 HP: ${bot.health}/20 | Food: ${bot.food}/20 | Mined: ${totalMined} | Inv: ${bot.inventory.items().length}/36`);
    }
  }, 60000); // Every minute
}

function updateScaffoldingBlocks() {
  const mcData = require('minecraft-data')(bot.version);
  const movements = new Movements(bot, mcData);
  
  // Copy existing settings
  movements.canDig = true;
  movements.allow1by1towers = true;
  movements.allowFreeMotion = true;
  movements.allowParkour = true;
  movements.allowSprinting = true;
  
  // Update scaffold items from current inventory
  movements.scaffoldingBlocks = [];
  const scaffoldItems = bot.inventory.items().filter(i => 
    i.name.includes('dirt') || 
    i.name.includes('cobblestone') || 
    i.name.includes('stone') ||
    i.name.includes('netherrack') ||
    i.name.includes('log')
  );
  scaffoldItems.forEach(item => movements.scaffoldingBlocks.push(item.type));
  
  bot.pathfinder.setMovements(movements);
}

async function clearPath(targetPos) {
  try {
    console.log('🔨 Attempting to clear path...');
    const direction = targetPos.minus(bot.entity.position).normalize();
    const checkPos = bot.entity.position.offset(direction.x * 2, 0, direction.z * 2);
    
    const blockingBlock = bot.blockAt(checkPos);
    if (blockingBlock && blockingBlock.name !== 'air' && blockingBlock.diggable) {
      console.log(`Breaking ${blockingBlock.name} that's in the way...`);
      await bot.dig(blockingBlock);
      await sleep(500);
    }
  } catch (err) {
    console.log('Could not clear path:', err.message);
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

startBot();