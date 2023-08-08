import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { Market } from 'src/market/entities/market.entity';
import { MarketController } from 'src/market/market.controller';
import { MarketService } from 'src/market/market.service';

@Module({
  imports: [TypeOrmModule.forFeature([Market])],
  controllers: [MarketController],
  providers: [MarketService],
  exports: [MarketService],
})
export class MarketModule {}
