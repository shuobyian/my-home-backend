import { Module, forwardRef } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { Market } from 'src/market/entities/market.entity';
import { MarketController } from 'src/market/market.controller';
import { MarketService } from 'src/market/market.service';
import { ResultModule } from 'src/result/result.module';

@Module({
  imports: [TypeOrmModule.forFeature([Market]), forwardRef(() => ResultModule)],
  controllers: [MarketController],
  providers: [MarketService],
  exports: [MarketService],
})
export class MarketModule {}
