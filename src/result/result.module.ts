import { Module, forwardRef } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { ItemModule } from 'src/item/item.module';
import { MarketModule } from 'src/market/market.module';
import { Result } from 'src/result/entities/result.entity';
import { ResultController } from 'src/result/result.controller';
import { ResultService } from 'src/result/result.service';

@Module({
  imports: [
    TypeOrmModule.forFeature([Result]),
    forwardRef(() => ItemModule),
    forwardRef(() => MarketModule),
  ],
  controllers: [ResultController],
  providers: [ResultService],
  exports: [ResultService],
})
export class ResultModule {}
