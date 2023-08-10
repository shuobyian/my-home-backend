import { Module, forwardRef } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { Item } from 'src/item/entities/item.entity';
import { ItemController } from 'src/item/item.controller';
import { ItemService } from 'src/item/item.service';
import { ResultModule } from 'src/result/result.module';

@Module({
  imports: [TypeOrmModule.forFeature([Item]), forwardRef(() => ResultModule)],
  controllers: [ItemController],
  providers: [ItemService],
  exports: [ItemService],
})
export class ItemModule {}
